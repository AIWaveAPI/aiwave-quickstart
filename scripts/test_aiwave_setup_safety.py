"""Offline safety checks against disposable settings, never a real user config."""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("aiwave-setup.py")
SPEC = importlib.util.spec_from_file_location("aiwave_setup", SCRIPT)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.claude = root / ".claude" / "settings.json"
        self.codex = root / ".codex" / "config.toml"
        self.claude.parent.mkdir()
        self.codex.parent.mkdir()
        setup.CLAUDE_SETTINGS = self.claude
        setup.CODEX_CONFIG = self.codex

    def capture(self, fn, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            fn(*args)
        return output.getvalue()

    def run_main(self, *args):
        with patch.dict(os.environ, {"AIWAVE_API_KEY": "synthetic-key"}), patch.object(sys, "argv", ["setup"] + list(args)):
            return self.capture(setup.main)

    def test_preview_hides_secrets_and_writes_nothing(self):
        sentinel = "PRIVATE_SENTINEL_ABC"
        original = json.dumps({"env": {"OTHER_SECRET": sentinel}})
        self.claude.write_text(original)
        output = self.run_main("--dry-run")
        self.assertNotIn(sentinel, output)
        self.assertNotIn("synthetic-key", output)
        self.assertIn("ANTHROPIC_BASE_URL", output)
        self.assertEqual(self.claude.read_text(), original)

    def test_default_setup_preserves_other_fields_and_restores_original(self):
        original = '{"env": {"ORIGINAL": "yes"}, "other": true}\n'
        self.claude.write_text(original)
        self.run_main()
        applied = json.loads(self.claude.read_text())
        self.assertEqual(applied["env"]["ANTHROPIC_AUTH_TOKEN"], "synthetic-key")
        self.assertEqual(applied["env"]["ORIGINAL"], "yes")
        self.assertTrue(applied["other"])
        self.assertEqual(len(list(self.claude.parent.glob("settings.json.aiwave.bak.*"))), 1)
        self.assertTrue(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_text(), original)

    def test_restore_refuses_later_edits(self):
        self.claude.write_text('{"env": {}}\n')
        self.run_main()
        applied = json.loads(self.claude.read_text())
        applied["env"]["LATER_SETTING"] = "keep"
        self.claude.write_text(json.dumps(applied))
        self.assertFalse(setup.restore_one(self.claude))
        self.assertEqual(json.loads(self.claude.read_text())["env"]["LATER_SETTING"], "keep")

    def test_key_rotation_keeps_pre_aiwave_backup(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        self.claude.write_text(original)
        self.run_main()
        self.capture(setup.setup_claude, "second-synthetic-key", False)
        self.assertEqual(len(list(self.claude.parent.glob("settings.json.aiwave.bak.*"))), 1)
        self.assertTrue(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_text(), original)

    def test_codex_and_both_refuse_before_any_write(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        codex_original = 'model = "original"\n'
        self.claude.write_text(original)
        self.codex.write_text(codex_original)
        for tool in ("codex", "both"):
            for extra in ((), ("--dry-run",)):
                with self.assertRaises(SystemExit) as caught:
                    self.run_main("--tool", tool, *extra)
                self.assertIn("No file changed", str(caught.exception))
                self.assertEqual(self.claude.read_text(), original)
                self.assertEqual(self.codex.read_text(), codex_original)
                self.assertEqual(list(self.claude.parent.glob("*.aiwave.*")), [])
                self.assertEqual(list(self.codex.parent.glob("*.aiwave.*")), [])

    def test_claude_setup_does_not_touch_old_codex_config(self):
        original = 'model_provider = "aiwave"\nwire_api = "chat"\n'
        self.codex.write_text(original)
        self.run_main()
        self.assertEqual(self.codex.read_text(), original)

    def test_symlinked_config_is_not_replaced(self):
        target = self.claude.parent / "managed-settings.json"
        target.write_text('{"env": {}}')
        try:
            self.claude.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(SystemExit):
            self.run_main()
        self.assertTrue(self.claude.is_symlink())
        self.assertEqual(target.read_text(), '{"env": {}}')

    def test_restore_refuses_tampered_backup(self):
        self.claude.write_text('{"env": {"ORIGINAL": "yes"}}\n')
        self.run_main()
        applied = self.claude.read_bytes()
        state = json.loads(setup.state_path(self.claude).read_text())
        Path(state["backup"]).write_text("different content")
        self.assertFalse(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_bytes(), applied)


if __name__ == "__main__":
    unittest.main()
