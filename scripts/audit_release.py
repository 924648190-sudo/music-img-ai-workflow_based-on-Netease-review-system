"""Check public source without printing any matched private values."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "personal_home_path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
    "email_address": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "credential_token": re.compile(r"\b(?:sk-|app-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{15,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}"),
    "literal_bearer": re.compile(r"Bearer\s+[A-Za-z0-9_-]{20,}"),
    "share_user_tracking": re.compile(r"[?&]userid=(?!0(?:[&#\s\"']|$))\d+", re.I),
    "real_share_shortlink": re.compile(r"https?(?:\\)?:/{2}163cn\.tv/(?!example)[A-Za-z0-9]+"),
    "assigned_secret": re.compile(r"(?im)^[ \t]*[\"']?(?:[A-Z][A-Z0-9_]*_)?(?:api_key|access_token|refresh_token|password|client_secret)[\"']?[ \t]*[:=][ \t]*[\"'][^\"'\n]{8,}[\"']"),
    "unquoted_environment_secret": re.compile(r"(?im)^[ \t]*(?:[A-Z][A-Z0-9_]*_)?(?:API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|PASSWORD|CLIENT_SECRET)[ \t]*=[ \t]*[^\s#\"']{8,}[ \t]*$"),
}
PRIVATE_DIRS = {"archive", "history", "verification", "research", "private", "logs", "outputs"}
PRIVATE_SUFFIXES = {".zip", ".xlsx", ".png", ".jpg", ".jpeg", ".pem", ".key", ".log"}
IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
PERSONAL_KEYS = {"tenant_id", "account_id", "workflow_run_id", "conversation_id", "created_by", "updated_by"}


def scan_text(text):
    return [(name, text.count("\n", 0, hit.start()) + 1)
            for name, pattern in RULES.items() for hit in pattern.finditer(text)]


def scan_config(value):
    issues = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PERSONAL_KEYS and child:
                issues.append("private_configuration_identifier")
            if key in {"environment_variables", "conversation_variables"} and isinstance(child, list):
                if any(isinstance(item, dict) and item.get("value") not in (None, "", []) for item in child):
                    issues.append("exported_runtime_variable_value")
            issues.extend(scan_config(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_config(child))
    return issues


def tracked_paths(root):
    # An accidentally tracked .env must fail even though a local .env is ignored.
    try:
        top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=root,
                                      stderr=subprocess.DEVNULL, text=True).strip()
        if Path(top).resolve() != root.resolve():
            return set()
        raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root,
                                      stderr=subprocess.DEVNULL)
        return set(raw.decode().rstrip("\0").split("\0")) - {""}
    except (OSError, subprocess.CalledProcessError):
        return set()


def scan_staged(root, tracked):
    """A clean working copy must not hide an older secret still in Git's index."""
    findings = []
    for name in sorted(tracked):
        path = Path(name)
        if (path.name.startswith(".env") and path.name != ".env.example"
                or any(part in PRIVATE_DIRS | IGNORED_DIRS for part in path.parts)
                or path.suffix.lower() in PRIVATE_SUFFIXES):
            continue
        result = subprocess.run(["git", "show", ":" + name], cwd=root,
                                capture_output=True)
        if result.returncode:
            findings.append((name, 1, "unreadable_git_index_entry"))
            continue
        local = root / name
        if local.is_file() and not local.is_symlink() and local.read_bytes() == result.stdout:
            continue
        try:
            text = result.stdout.decode("utf-8")
        except UnicodeError:
            findings.append((name, 1, "unreviewed_git_index_binary"))
            continue
        findings.extend((name, line, "git_index_" + rule) for rule, line in scan_text(text))
        if path.suffix == ".json":
            try:
                findings.extend((name, 1, "git_index_" + rule) for rule in scan_config(json.loads(text)))
            except ValueError:
                findings.append((name, 1, "git_index_invalid_json"))
    return findings


def main():
    tracked = tracked_paths(ROOT)
    findings, checked = [], 0
    for name in sorted(tracked):
        path = Path(name)
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append((name, 1, "tracked_environment_file"))
        elif (any(part in PRIVATE_DIRS | IGNORED_DIRS for part in path.parts)
              or path.suffix.lower() in PRIVATE_SUFFIXES):
            findings.append((name, 1, "tracked_private_artifact"))
    for path in sorted(ROOT.rglob("*")):
        if path.is_symlink():
            findings.append((str(path.relative_to(ROOT)), 1, "unreviewed_symlink"))
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.name == ".DS_Store" or path.suffix == ".pyc":
            continue
        checked += 1
        if any(part in PRIVATE_DIRS for part in rel.parts) or path.suffix.lower() in PRIVATE_SUFFIXES:
            findings.append((str(rel), 1, "private_artifact_in_release"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            findings.append((str(rel), 1, "unreviewed_binary"))
            continue
        findings.extend((str(rel), line, rule) for rule, line in scan_text(text))
        if path.suffix == ".json":
            try:
                findings.extend((str(rel), 1, issue) for issue in scan_config(json.loads(text)))
            except ValueError:
                findings.append((str(rel), 1, "invalid_json"))
    findings.extend(scan_staged(ROOT, tracked))
    print(json.dumps({"checked_files": checked, "findings": [
        {"file": name, "line": line, "rule": rule} for name, line, rule in findings
    ]}, ensure_ascii=False, indent=2))
    return bool(findings)


if __name__ == "__main__":
    sys.exit(main())
