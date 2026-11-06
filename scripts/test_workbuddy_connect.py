"""Offline tests. Every write targets a temporary directory, never a real profile."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts import workbuddy_connect as wb


def catalog():
    def row(name, groups, endpoints):
        return {"model_name": name, "enable_groups": groups,
                "supported_endpoint_types": endpoints, "quota_type": 0,
                "model_ratio": 0.5, "completion_ratio": 2, "model_price": 0}
    return {"success": True, "pricing_version": "test-version", "group_ratio": {"default": 1},
            "data": [row("deepseek-v4.1-flash", ["default"], ["openai"]),
                     row("deepseek-v4-pro", ["default"], ["openai"]),
                     row("claude-sonnet-5-coding-team", ["coding team"], ["openai"]),
                     row("video-only", ["default"], ["video"])]}


class CatalogTests(unittest.TestCase):
    def test_only_default_openai_models_are_eligible(self):
        names = wb.eligible_model_ids(catalog())
        self.assertEqual(names, ["deepseek-v4-pro", "deepseek-v4.1-flash"])

    def test_explicit_model_must_be_eligible(self):
        with self.assertRaises(wb.ConnectError):
            wb.select_model_ids(catalog(), ["claude-sonnet-5-coding-team"], False)

    def test_default_set_is_small(self):
        self.assertEqual(wb.select_model_ids(catalog(), None),
                         ["deepseek-v4.1-flash", "deepseek-v4-pro"])

    def test_non_chat_model_is_not_installable_even_with_endpoint_label(self):
        data = catalog()
        data["data"].append({"model_name": "qwen3.7-text-embedding",
                             "enable_groups": ["default"],
                             "supported_endpoint_types": ["openai"]})
        with self.assertRaises(wb.ConnectError):
            wb.select_model_ids(data, ["qwen3.7-text-embedding"])

    def test_missing_group_multiplier_never_becomes_a_price(self):
        data = catalog()
        del data["group_ratio"]["default"]
        self.assertIsNone(wb.default_group_ratio(data))
        self.assertIn("unverified", wb.rate_text(data["data"][0], wb.default_group_ratio(data)))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "models.json"
        self.other = {"id": "other-model", "name": "Other", "vendor": "Other",
                      "url": "https://other.example/v1", "apiKey": "other-secret"}
        self.original = json.dumps([self.other], separators=(",", ":")).encode()
        self.path.write_bytes(self.original)
        self.store = wb.ConfigStore(self.path)

    def test_install_preserves_other_models_and_undo_preserves_later_edits(self):
        ids = wb.select_model_ids(catalog(), None, False)
        result = self.store.install(ids, "customer-secret")
        self.assertEqual(result["added"], 2)
        entries = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(entries[0], self.other)
        self.assertEqual([e["id"] for e in entries[1:]], ids)
        self.assertTrue(all(e["supportsToolCall"] is False for e in entries[1:]))
        self.assertTrue(all(e["useCustomProtocol"] is True for e in entries[1:]))
        state = (self.path.parent / ".aiwave-connect-state.json").read_text()
        self.assertNotIn("customer-secret", state)
        self.assertNotIn("other-secret", state)
        self.assertEqual(len(list(self.path.parent.glob("models.json.aiwave-backup-*"))), 1)
        entries.append({"id": "later", "vendor": "Other", "apiKey": "later-secret"})
        self.path.write_text(json.dumps(entries), encoding="utf-8")
        undone = self.store.undo()
        self.assertEqual(undone["removed"], 2)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")),
                         [self.other, {"id": "later", "vendor": "Other", "apiKey": "later-secret"}])

    def test_repeat_install_is_idempotent(self):
        ids = wb.select_model_ids(catalog(), None, False)
        self.store.install(ids, "customer-secret")
        before = self.path.read_bytes()
        self.assertEqual(self.store.install(ids, "customer-secret")["added"], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_collision_does_not_modify_file(self):
        self.path.write_text(json.dumps([{"id": "deepseek-v4-pro", "vendor": "Other"}]),
                             encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(wb.ConnectError):
            self.store.install(["deepseek-v4-pro"], "customer-secret")
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_manual_aiwave_entry_is_preserved_not_owned(self):
        manual = {"id": "deepseek-v4-pro", "name": "My Pro", "vendor": "Custom",
                  "url": "https://aiwave.live/v1/chat/completions", "apiKey": "older-own-key"}
        self.path.write_text(json.dumps([self.other, manual]), encoding="utf-8")
        result = self.store.install(["deepseek-v4.1-flash", "deepseek-v4-pro"], "new-own-key")
        self.assertEqual(result["added"], 1)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))[1], manual)
        self.store.undo()
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), [self.other, manual])

    def test_malformed_existing_url_cannot_crash_or_be_adopted(self):
        bad = {"id": "deepseek-v4-pro", "vendor": "Custom",
               "url": "https://aiwave.live:bad/v1", "apiKey": "old-secret"}
        self.path.write_text(json.dumps([bad]), encoding="utf-8")
        with self.assertRaises(wb.ConnectError):
            self.store.install(["deepseek-v4-pro"], "customer-secret")

    def test_malformed_file_does_not_modify_file(self):
        self.path.write_text("not-json", encoding="utf-8")
        with self.assertRaises(wb.ConnectError):
            self.store.install(["deepseek-v4-pro"], "customer-secret")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "not-json")

    def test_undo_refuses_modified_owned_entry(self):
        self.store.install(["deepseek-v4-pro"], "customer-secret")
        entries = json.loads(self.path.read_text(encoding="utf-8"))
        entries[-1]["name"] = "My custom name"
        self.path.write_text(json.dumps(entries), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(wb.ConnectError):
            self.store.undo()
        self.assertEqual(self.path.read_bytes(), before)

    def test_symlink_is_refused(self):
        target = self.path.parent / "actual.json"
        target.write_bytes(self.original)
        link = self.path.parent / "link.json"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(wb.ConnectError):
            wb.ConfigStore(link).install(["deepseek-v4-pro"], "customer-secret")


if __name__ == "__main__":
    unittest.main()
