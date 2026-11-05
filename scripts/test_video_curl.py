"""Offline end-to-end check of the shell example with fake curl and sleep."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

if os.name == "nt" or not shutil.which("bash"):
    print("SKIP: requires bash")
    raise SystemExit(0)

script = Path(__file__).resolve().parent / "video_curl.sh"
prompt = 'He said "go" \\ backslash\nnext line'
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    fake_curl = root / "curl"
    fake_sleep = root / "sleep"
    fake_curl.write_text(
        "#!/usr/bin/env python3\n"
        "import json,os,sys\n"
        "from pathlib import Path\n"
        "a=sys.argv[1:]\n"
        "with Path(os.environ['CALLS']).open('a') as f: f.write('POST\\n' if '--data-binary' in a else 'GET\\n')\n"
        "if '--data-binary' in a:\n"
        "  Path(os.environ['PAYLOAD']).write_text(a[a.index('--data-binary')+1])\n"
        "  if os.environ.get('FAIL_SUBMIT'): sys.exit(22)\n"
        "  print(json.dumps({'task_id':'task-123'}))\n"
        "else: print(json.dumps({'data':{'status':'SUCCESS','progress':'100%','url':'https://example.test/result.mp4'}}))\n"
    )
    fake_sleep.write_text("#!/bin/sh\nexit 0\n")
    fake_curl.chmod(0o755)
    fake_sleep.chmod(0o755)
    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
               AIWAVE_API_KEY="synthetic-key", CALLS=str(root / "calls"),
               PAYLOAD=str(root / "payload"))
    result = subprocess.run(["bash", str(script), prompt], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json.loads((root / "payload").read_text())["prompt"] == prompt
    assert (root / "calls").read_text().splitlines() == ["POST", "GET"]
    assert "task-123" in result.stdout and "result.mp4" in result.stdout

    (root / "calls").unlink()
    env["FAIL_SUBMIT"] = "1"
    failed = subprocess.run(["bash", str(script), prompt], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert failed.returncode != 0
    assert "outcome unknown" in failed.stderr.lower()
    assert (root / "calls").read_text().splitlines() == ["POST"]
print("PASS: JSON prompt, task/status parse, uncertain POST never retried")
