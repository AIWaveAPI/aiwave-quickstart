"""Check the public setup command in a disposable HOME, never real configs."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

script = Path(__file__).with_name("aiwave-setup.py")
spec = importlib.util.spec_from_file_location("setup", script)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

with tempfile.TemporaryDirectory() as td:
    config = Path(td) / ".claude" / "settings.json"
    config.parent.mkdir()
    original = '{"skipWorkflowUsageWarning": true}\n'
    config.write_text(original)
    setup.CLAUDE_SETTINGS = config
    with patch.dict(os.environ, {"AIWAVE_API_KEY": "synthetic-key"}):
        with patch.object(sys, "argv", ["setup", "--dry-run"]):
            with contextlib.redirect_stdout(io.StringIO()):
                setup.main()
        assert config.read_text() == original
        with patch.object(sys, "argv", ["setup"]):
            with contextlib.redirect_stdout(io.StringIO()):
                setup.main()
        configured = json.loads(config.read_text())
        assert configured["skipWorkflowUsageWarning"] is True
        assert configured["env"]["ANTHROPIC_BASE_URL"] == "https://aiwave.live/anthropic"
        assert configured["env"]["ANTHROPIC_AUTH_TOKEN"] == "synthetic-key"
        assert setup.restore_one(config)
        assert config.read_text() == original
print("PASS: dry-run, Claude setup, existing fields and exact restore")
