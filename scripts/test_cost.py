"""Fail-closed cost estimates for a named, catalog-eligible account group."""

import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from scripts import cost


CATALOG = {
    "pricing_version": "fixture-version",
    "group_ratio": {"default": 1, "Visual Team": 0.9},
    "data": [
        {"model_name": "deepseek-v4-flash", "quota_type": 0,
         "model_ratio": 0.15, "completion_ratio": 4, "cache_ratio": 0.02,
         "enable_groups": ["default", "Visual Team"]},
        {"model_name": "kling-v2-6", "quota_type": 1,
         "model_price": 0.2, "enable_groups": ["Visual Team"]},
    ],
}


class CostSafetyTests(unittest.TestCase):
    def run_cli(self, *args, catalog=CATALOG):
        output = io.StringIO()
        with patch.object(sys, "argv", ["cost.py", *args]), patch.object(cost, "fetch", return_value=catalog):
            with contextlib.redirect_stdout(output):
                cost.main()
        return output.getvalue()

    def test_token_rate_uses_named_group_ratio(self):
        kind, rates = cost.price_of(CATALOG["data"][0], "Visual Team", CATALOG["group_ratio"])
        self.assertEqual(kind, "per_token")
        self.assertAlmostEqual(rates["input"], 0.27)
        self.assertAlmostEqual(rates["output"], 1.08)

    def test_unavailable_or_unknown_group_cannot_receive_quote(self):
        with self.assertRaisesRegex(ValueError, "not enabled"):
            cost.price_of(CATALOG["data"][1], "default", CATALOG["group_ratio"])
        with self.assertRaisesRegex(ValueError, "ratio"):
            cost.price_of(CATALOG["data"][1], "vip", CATALOG["group_ratio"])

    def test_missing_price_never_becomes_zero_dollar_quote(self):
        bad = {**CATALOG["data"][1], "model_price": 0}
        with self.assertRaisesRegex(ValueError, "price"):
            cost.price_of(bad, "Visual Team", CATALOG["group_ratio"])
        with self.assertRaisesRegex(ValueError, "group ratio"):
            cost.price_of(CATALOG["data"][1], "Visual Team", {})

    def test_missing_cache_rate_is_only_required_when_cache_hits_requested(self):
        no_cache_rate = {key: value for key, value in CATALOG["data"][0].items()
                         if key != "cache_ratio"}
        kind, rates = cost.price_of(no_cache_rate, "default", CATALOG["group_ratio"])
        self.assertEqual(kind, "per_token")
        self.assertIsNone(rates["cache"])
        self.assertGreater(cost.cost_token(rates, 100, 800, 300, 0), 0)
        with self.assertRaisesRegex(ValueError, "cache"):
            cost.cost_token(rates, 100, 800, 300, 0.5)

    def test_video_preset_without_clips_uses_ten_not_messages_default(self):
        output = self.run_cli("--preset", "video", "--model", "kling-v2-6",
                              "--group", "Visual Team")
        self.assertIn("10 clips/day", output)
        self.assertIn("10 calls", output)
        self.assertIn("$1.80", output)  # 0.2 base price × 0.9 group × 10 clips
        self.assertIn("fixture-version", output)
        self.assertIn("Visual Team", output)

    def test_wrong_workload_kind_and_negative_quantity_fail(self):
        with self.assertRaisesRegex(SystemExit, "per-call"):
            self.run_cli("--model", "kling-v2-6", "--group", "Visual Team")
        with self.assertRaisesRegex(SystemExit, "token-priced"):
            self.run_cli("--preset", "video", "--model", "deepseek-v4-flash")
        with self.assertRaisesRegex(SystemExit, "--days"):
            self.run_cli("--model", "deepseek-v4-flash", "--days", "-1")
        with self.assertRaisesRegex(SystemExit, "--clips"):
            self.run_cli("--preset", "video", "--model", "kling-v2-6",
                         "--group", "Visual Team", "--clips", "-2")
        with self.assertRaisesRegex(SystemExit, "both be zero"):
            self.run_cli("--model", "deepseek-v4-flash", "--avg-input", "0",
                         "--avg-output", "0")

    def test_small_positive_estimate_is_not_rendered_as_free(self):
        self.assertNotEqual(cost.fmt(0.000000001), "$0.0000")
        self.assertIn("e-", cost.fmt(0.000000001))


if __name__ == "__main__":
    unittest.main()
