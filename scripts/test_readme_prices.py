"""Offline regression tests for the README's explicitly priced model rows."""

import unittest

from scripts.verify_readme_prices import check_prices


README = """## 3. Choose a model

Popular picks (reasoning & chat):

| Model | Best for | Rate |
|---|---|---|
| `deepseek-v4-flash` | Fast | $0.30 / $1.20 per 1M |
| `deepseek-v4-pro` | Reasoning | $1.32 / $3.96 per 1M |
| `kimi-k3` | Long context | see [pricing](https://aiwave.live/pricing) |

## 5. AI video
"""

CATALOG = {
    "data": [
        {"model_name": "deepseek-v4-flash", "quota_type": 0,
         "model_ratio": 0.15, "completion_ratio": 4,
         "enable_groups": ["default"]},
        {"model_name": "deepseek-v4-pro", "quota_type": 0,
         "model_ratio": 0.66, "completion_ratio": 3,
         "enable_groups": ["default"]},
    ],
    "group_ratio": {"default": 1},
}


class ReadmePriceTests(unittest.TestCase):
    def test_current_rates_match(self):
        checked, errors = check_prices(README, CATALOG)
        self.assertEqual(checked, 2)
        self.assertEqual(errors, [])

    def test_wrong_output_rate_reports_line(self):
        checked, errors = check_prices(README.replace("$3.96", "$3.95"), CATALOG)
        self.assertEqual(checked, 2)
        self.assertTrue(any("deepseek-v4-pro" in error and "3.95" in error
                            and "line" in error for error in errors), errors)

    def test_default_group_multiplier_drift_is_detected(self):
        _, errors = check_prices(README, {**CATALOG, "group_ratio": {"default": 1.1}})
        self.assertTrue(any("deepseek-v4-flash" in error for error in errors), errors)

    def test_missing_route_or_default_group_fails_closed(self):
        _, missing = check_prices(README, {**CATALOG, "data": CATALOG["data"][:1]})
        self.assertTrue(any("deepseek-v4-pro" in error for error in missing))
        unavailable = {**CATALOG, "data": [{**CATALOG["data"][0],
                                             "enable_groups": ["vip"]}, CATALOG["data"][1]]}
        _, errors = check_prices(README, unavailable)
        self.assertTrue(any("default" in error for error in errors))

    def test_per_call_and_malformed_rate_fail_closed(self):
        per_call = {**CATALOG, "data": [{**CATALOG["data"][0], "quota_type": 1},
                                          CATALOG["data"][1]]}
        _, errors = check_prices(README, per_call)
        self.assertTrue(any("per-call" in error for error in errors), errors)
        _, errors = check_prices(README.replace("$0.30 / $1.20 per 1M", "$0.30 per 1M"),
                                 CATALOG)
        self.assertTrue(any("unparseable" in error for error in errors), errors)

    def test_empty_or_duplicate_table_fails(self):
        _, errors = check_prices("## 3. Choose a model\nNo table\n", CATALOG)
        self.assertTrue(errors)
        row = "| `deepseek-v4-flash` | Fast | $0.30 / $1.20 per 1M |"
        _, errors = check_prices(README.replace(row, row + "\n" + row), CATALOG)
        self.assertTrue(any("duplicate" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
