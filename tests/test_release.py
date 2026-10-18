import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


client = module("run_workflow")
audit = module("audit_release")


class ReleaseChecks(unittest.TestCase):
    def test_env_does_not_execute_or_override_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('DIFY_API_KEY="file-value"\nEXAMPLE_LITERAL=$(false)\n')
            with patch.dict(os.environ, {"DIFY_API_KEY": "process-value"}, clear=True):
                client.load_env(path)
                self.assertEqual(os.environ["DIFY_API_KEY"], "process-value")
                self.assertEqual(os.environ["EXAMPLE_LITERAL"], "$(false)")

    def test_key_required_and_used_only_in_header(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                client.make_request("example")
        with patch.dict(os.environ, {"DIFY_API_KEY": "unit-test-key"}, clear=True):
            request = client.make_request("example", "")
            self.assertEqual(request.get_header("Authorization"), "Bearer unit-test-key")
            body = json.loads(request.data)
            self.assertEqual(body["inputs"], {"userinput_query": "example", "song_url": ""})
            self.assertNotIn("unit-test-key", request.data.decode())
            self.assertEqual(body["response_mode"], "blocking")
            self.assertNotEqual(body["user"], json.loads(client.make_request("example").data)["user"])

    def test_unsafe_base_urls_rejected(self):
        urls = ["http://example.invalid/v1", "https://user:pass" + "@" + "example.invalid/v1",
                "https://example.invalid/v1?x=1", "https://example.invalid/v1#fragment"]
        for url in urls:
            with patch.dict(os.environ, {"DIFY_API_KEY": "unit-test-key", "DIFY_API_BASE_URL": url}, clear=True):
                with self.assertRaises(ValueError):
                    client.make_request("example")
        self.assertIsNone(client.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid"))

    def test_only_final_output_is_returned(self):
        data = {"status": "succeeded", "outputs": {"prompt": "result"}, "private_trace": "not returned"}
        self.assertEqual(client.extract_outputs({"data": data}), {"prompt": "result"})
        for status in ["failed", "stopped", "running"]:
            with self.assertRaises(ValueError):
                client.extract_outputs({"data": {"status": status, "error": "private detail"}})

    def test_scan_detects_synthetic_secrets_without_echoing(self):
        secret = "s" + "k-" + "Z" * 25
        email = "person" + "@" + "example.invalid"
        findings = audit.scan_text(secret + "\n" + email)
        self.assertIn(("credential_token", 1), findings)
        self.assertIn(("email_address", 2), findings)
        self.assertNotIn(secret, repr(findings))
        self.assertNotIn(email, repr(findings))

    def test_exported_private_variables_rejected(self):
        self.assertTrue(audit.scan_config({"environment_variables": [{"value": "unit-test-key"}]}))
        self.assertFalse(audit.scan_config({"environment_variables": []}))

    def test_uppercase_and_unquoted_environment_keys_detected(self):
        value = "synthetic-" + "value-for-audit"
        for setting in ['DIFY_' + 'API_KEY="' + value + '"',
                        'DEEPSEEK_' + 'API_KEY=' + value]:
            self.assertTrue(audit.scan_text(setting))
        self.assertFalse(audit.scan_text('DIFY_' + 'API_KEY=\nDIFY_API_TIMEOUT=360\n'))

    def test_tracked_environment_rejected_even_when_missing_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(audit, "ROOT", root), patch.object(audit, "tracked_paths", return_value={".env"}):
                with patch("builtins.print"):
                    self.assertTrue(audit.main())

    def test_symlink_not_scanned_as_public_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside").symlink_to(root.parent / "nonexistent-private-file")
            with patch.object(audit, "ROOT", root), patch.object(audit, "tracked_paths", return_value=set()):
                with patch("builtins.print"):
                    self.assertTrue(audit.main())

    def test_staged_secret_detected_after_working_file_was_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
            config = root / "settings.py"
            config.write_text('DIFY_' + 'API_KEY="' + 'synthetic-value-for-index' + '"\n')
            subprocess.run(["git", "add", "settings.py"], cwd=root, check=True, capture_output=True)
            config.write_text('# no credentials\n')
            findings = audit.scan_staged(root, {"settings.py"})
            self.assertTrue(any(rule == "git_index_assigned_secret" for _, _, rule in findings))

    def test_workflow_has_no_embedded_auth(self):
        workflow = json.loads((ROOT / "workflow-3.1.json").read_text())
        self.assertEqual(workflow["workflow"]["environment_variables"], [])
        for node in workflow["workflow"]["graph"]["nodes"]:
            data = node["data"]
            if data["type"] == "http-request":
                self.assertEqual(data["authorization"]["type"], "no-auth")
                self.assertNotIn("authorization:", data.get("headers", "").lower())


if __name__ == "__main__":
    unittest.main()
