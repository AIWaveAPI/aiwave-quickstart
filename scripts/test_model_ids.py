"""Regression checks for negative model-ID statements sharing a Markdown line."""

import unittest

from scripts.verify_model_ids import IN_CODE, is_negated_id


class NegativeModelIdTests(unittest.TestCase):
    def test_negative_example_does_not_exempt_neighboring_id(self):
        line = "There is no `qwen3-coder` ID, but `qwen3-bogus` is available."
        matches = list(IN_CODE.finditer(line))
        self.assertEqual([is_negated_id(line, m) for m in matches], [True, False])

    def test_suffix_negative_statement(self):
        line = "`qwen3-coder` is not on our card; `qwen3-bogus` is available."
        matches = list(IN_CODE.finditer(line))
        self.assertEqual([is_negated_id(line, m) for m in matches], [True, False])


if __name__ == "__main__":
    unittest.main()

