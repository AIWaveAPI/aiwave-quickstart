"""Safety checks for the setup script using only disposable configurations."""

import contextlib
import importlib.util
import io
import json
import os
import re
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
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def test_preview_never_prints_unrelated_existing_secret(self):
        sentinel = "PRIVATE_SENTINEL_ABC"
        self.claude.write_text(json.dumps({"env": {"OTHER_SECRET": sentinel}}))
        output = self.capture(setup.setup_claude, "synthetic-key", True)
        self.assertNotIn(sentinel, output)
        self.assertIn("ANTHROPIC_BASE_URL", output)

    def test_existing_codex_provider_and_model_switch_together(self):
        self.codex.write_text('model_provider = "other"\nmodel = "other-model"\n\n[features]\nfoo = true\n')
        self.capture(setup.setup_codex, "synthetic-key", False)
        top = self.codex.read_text().split("[", 1)[0]
        self.assertEqual(re.findall(r'^model_provider\s*=\s*"([^"]+)"', top, re.M), ["aiwave"])
        self.assertEqual(re.findall(r'^model\s*=\s*"([^"]+)"', top, re.M), [setup.CODEX_MODEL])

    def test_restore_refuses_to_erase_edits_made_after_setup(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        self.claude.write_text(original)
        self.capture(setup.setup_claude, "synthetic-key", False)
        after = json.loads(self.claude.read_text())
        after["env"]["NEW_LATER_SETTING"] = "keep"
        self.claude.write_text(json.dumps(after))
        self.assertFalse(setup.restore_one(self.claude))
        self.assertEqual(json.loads(self.claude.read_text())["env"]["NEW_LATER_SETTING"], "keep")

    def test_restore_unchanged_applied_config(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        self.claude.write_text(original)
        self.capture(setup.setup_claude, "synthetic-key", False)
        self.assertTrue(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_text(), original)

    def test_repeated_setup_does_not_add_another_provider_or_backup(self):
        self.codex.write_text('model_provider = "other"\nmodel = "other-model"\n')
        self.capture(setup.setup_codex, "synthetic-key", False)
        first = self.codex.read_bytes()
        self.capture(setup.setup_codex, "synthetic-key", False)
        self.assertEqual(self.codex.read_bytes(), first)
        self.assertEqual(first.count(b"[model_providers.aiwave]"), 1)
        self.assertEqual(len(list(self.codex.parent.glob("config.toml.aiwave.bak.*"))), 1)

    def test_restore_new_file_removes_only_unchanged_setup(self):
        self.capture(setup.setup_codex, "synthetic-key", False)
        self.assertTrue(self.codex.exists())
        self.assertTrue(setup.restore_one(self.codex))
        self.assertFalse(self.codex.exists())

    def test_modified_config_blocks_repeated_setup(self):
        self.capture(setup.setup_claude, "synthetic-key", False)
        self.claude.write_text(self.claude.read_text() + " ")
        modified = self.claude.read_bytes()
        with self.assertRaises(SystemExit):
            self.capture(setup.setup_claude, "synthetic-key", False)
        self.assertEqual(self.claude.read_bytes(), modified)

    def test_key_rotation_still_restores_pre_aiwave_config(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        self.claude.write_text(original)
        self.capture(setup.setup_claude, "synthetic-key-one", False)
        self.capture(setup.setup_claude, "synthetic-key-two", False)
        self.assertTrue(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_text(), original)

    def test_existing_aiwave_provider_must_use_the_expected_key_variable(self):
        before = ('model_provider = "other"\nmodel = "other-model"\n'
                  '[model_providers.aiwave]\nname = "AIWave"\n'
                  'base_url = "https://aiwave.live/v1"\nwire_api = "chat"\n'
                  'env_key = "UNRELATED_VARIABLE"\n')
        self.codex.write_text(before)
        with self.assertRaises(SystemExit):
            self.capture(setup.setup_codex, "synthetic-key", False)
        self.assertEqual(self.codex.read_text(), before)

    def test_comment_cannot_disguise_wrong_existing_key_variable(self):
        before = ('[model_providers.aiwave]\nname = "AIWave"\n'
                  'base_url = "https://aiwave.live/v1"\nwire_api = "chat"\n'
                  'env_key = "UNRELATED_VARIABLE"\n# env_key = "AIWAVE_API_KEY"\n')
        self.codex.write_text(before)
        with self.assertRaises(SystemExit):
            self.capture(setup.setup_codex, "synthetic-key", False)
        self.assertEqual(self.codex.read_text(), before)

    def test_both_tools_preflight_before_changing_either_file(self):
        original = '{"env": {"ORIGINAL": "yes"}}\n'
        self.claude.write_text(original)
        self.codex.write_text('[model_providers.aiwave]\nbase_url = "wrong"\nwire_api = "chat"\n')
        with patch.dict(os.environ, {"AIWAVE_API_KEY": "synthetic-key"}), patch.object(sys, "argv", ["setup", "--tool", "both"]):
            with self.assertRaises(SystemExit):
                self.capture(setup.main)
        self.assertEqual(self.claude.read_text(), original)

    def test_symlinked_config_is_not_replaced(self):
        target = self.claude.parent / "managed-settings.json"
        target.write_text('{"env": {}}')
        try:
            self.claude.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unavailable in this environment")
        with self.assertRaises(SystemExit):
            self.capture(setup.setup_claude, "synthetic-key", False)
        self.assertTrue(self.claude.is_symlink())
        self.assertEqual(target.read_text(), '{"env": {}}')

    def test_restore_refuses_tampered_backup(self):
        self.claude.write_text('{"env": {"ORIGINAL": "yes"}}\n')
        self.capture(setup.setup_claude, "synthetic-key", False)
        applied = self.claude.read_bytes()
        state = json.loads(setup.state_path(self.claude).read_text())
        Path(state["backup"]).write_text("different content")
        self.assertFalse(setup.restore_one(self.claude))
        self.assertEqual(self.claude.read_bytes(), applied)


if __name__ == "__main__":
    unittest.main()
