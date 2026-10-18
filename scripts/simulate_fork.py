"""Simulate a clean local Git clone with no real API calls or credentials."""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''
import contextlib, importlib.util, io, json, os, socket, sys
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);mode=sys.argv[2]
spec=importlib.util.spec_from_file_location('client',root/'scripts/run_workflow.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
network_attempts=[];requests=[]
def deny(*args,**kwargs):
    network_attempts.append(1)
    raise AssertionError('Network is disabled during fork simulation')
class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
class Opener:
    def open(self,request,timeout):
        requests.append(request)
        assert mode=='own-key'
        assert request.full_url=='https://fork.example.invalid/v1/workflows/run'
        assert request.get_header('Authorization')=='Bearer '+os.environ['DIFY_API_KEY']
        body=json.loads(request.data)
        assert body['inputs']==json.loads((root/'examples/input.json').read_text())
        assert os.environ['DIFY_API_KEY'] not in request.data.decode()
        assert body['user'].startswith('cli-')
        return Response(json.dumps({'data':{'status':'succeeded','outputs':{'prompt':'mock-result'}}}).encode())
stdout=io.StringIO();stderr=io.StringIO()
with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny),patch.object(client,'build_opener',return_value=Opener()),patch.object(sys,'argv',['client','--input-file',str(root/'examples/input.json')]),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
    result=client.main()
if mode=='no-key':
    assert result==1 and not requests and not stdout.getvalue()
else:
    assert result==0 and len(requests)==1
    assert json.loads(stdout.getvalue())=={'prompt':'mock-result'}
    assert os.environ['DIFY_API_KEY'] not in stdout.getvalue()+stderr.getvalue()
assert not network_attempts
print(json.dumps({'mode':mode,'exit_status':result,'mock_requests':len(requests),'real_network_attempts':len(network_attempts)}))
'''


def run(args, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        # Do not echo subprocess output, which could include future secret values.
        raise RuntimeError("Fork simulation step failed: " + Path(args[0]).name)
    return result.stdout


def ignore_local(directory, names):
    excluded = {".git", "node_modules", ".venv", "venv", "__pycache__", ".DS_Store"}
    return [name for name in names if name in excluded
            or (name.startswith(".env") and name != ".env.example")]


def main():
    with tempfile.TemporaryDirectory(prefix="workflow-fork-simulation-") as temp:
        base = Path(temp)
        env = {"PATH": os.defpath, "HOME": str(base), "LANG": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_AUTHOR_NAME": "ForkSimulation", "GIT_COMMITTER_NAME": "ForkSimulation",
               "GIT_AUTHOR_EMAIL": "fork" + "@" + "example.invalid",
               "GIT_COMMITTER_EMAIL": "fork" + "@" + "example.invalid"}
        source, clone = base / "source", base / "fork"
        shutil.copytree(ROOT, source, ignore=ignore_local)
        # Synthetic, random canary; not a real key and never printed.
        canary = secrets.token_urlsafe(32)
        (source / ".env").write_text("DIFY_API_KEY=" + canary + "\n")
        run(["git", "-c", "init.defaultBranch=main", "init", "-q"], source, env)
        run(["git", "check-ignore", ".env"], source, env)
        run(["git", "add", "."], source, env)
        run(["git", "commit", "-qm", "Public source fork simulation"], source, env)
        for row in run(["git", "rev-list", "--objects", "--all"], source, env).splitlines():
            content = subprocess.check_output(["git", "cat-file", "-p", row.split()[0]], cwd=source, env=env,
                                              stderr=subprocess.DEVNULL)
            if canary.encode() in content:
                raise RuntimeError("A local credential entered Git objects")
        run(["git", "clone", "--no-hardlinks", "-q", str(source), str(clone)], base, env)
        assert not (clone / ".env").exists()
        tracked = run(["git", "ls-files"], clone, env).splitlines()
        for relative in tracked:
            assert (clone / relative).read_bytes() == (source / relative).read_bytes()
        before = json.loads((clone / "workflow-3.1.json").read_text())
        run(["ruby", "-rjson", "-ryaml", "-e",
             'abort "DSL differs" unless YAML.load_file(ARGV[0])==JSON.parse(File.read(ARGV[1]))',
             "music-visual-style-3.1.yml", "workflow-3.1.json"], clone, env)
        run([sys.executable, "-B", "scripts/audit_release.py"], clone, env)
        run([sys.executable, "-B", "build_31.py"], clone, env)
        after = json.loads((clone / "workflow-3.1.json").read_text())
        assert before == after
        run([sys.executable, "-B", "test_31.py"], clone, env)
        run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], clone, env)
        run([sys.executable, "-B", "scripts/audit_release.py"], clone, env)
        probe = base / "probe.py"
        probe.write_text(PROBE)
        no_key = json.loads(run([sys.executable, "-B", str(probe), str(clone), "no-key"], clone, env))
        own_env = dict(env, DIFY_API_KEY=secrets.token_urlsafe(32),
                       DIFY_API_BASE_URL="https://fork.example.invalid/v1")
        own_key = json.loads(run([sys.executable, "-B", str(probe), str(clone), "own-key"], clone, own_env))
        print(json.dumps({
            "git_clone_complete": True, "tracked_files": len(tracked),
            "private_env_excluded_from_git_objects": True,
            "yaml_json_equivalent": True, "clean_rebuild_identical": True,
            "nodes": len(after["workflow"]["graph"]["nodes"]),
            "edges": len(after["workflow"]["graph"]["edges"]),
            "source_sha256": hashlib.sha256((ROOT / "workflow-3.1.json").read_bytes()).hexdigest(),
            "regression_tests": "passed", "privacy_scan": "passed",
            "without_credentials": no_key, "with_fork_owner_mock_credentials": own_key,
            "real_api_calls": 0, "publisher_tokens_consumed": 0,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
