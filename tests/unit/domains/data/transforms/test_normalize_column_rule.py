"""Tests for NormalizeColumnRule."""

from __future__ import annotations

import unittest

from pirn_data.transforms.normalize_column_rule import NormalizeColumnRule


class TestNormalizeColumnRuleConstruction(unittest.TestCase):
    def test_defaults(self) -> None:
        r = NormalizeColumnRule()
        self.assertFalse(r.strip_whitespace)
        self.assertIsNone(r.case)
        self.assertEqual(r.null_tokens, ())
        self.assertFalse(r.null_tokens_case_sensitive)

    def test_valid_case_lower(self) -> None:
        r = NormalizeColumnRule(case="lower")
        self.assertEqual(r.case, "lower")

    def test_valid_case_upper(self) -> None:
        r = NormalizeColumnRule(case="upper")
        self.assertEqual(r.case, "upper")

    def test_valid_case_title(self) -> None:
        r = NormalizeColumnRule(case="title")
        self.assertEqual(r.case, "title")

    def test_case_none_allowed(self) -> None:
        r = NormalizeColumnRule(case=None)
        self.assertIsNone(r.case)

    def test_invalid_case_raises(self) -> None:
        with self.assertRaises(ValueError):
            NormalizeColumnRule(case="snake")

    def test_null_tokens(self) -> None:
        r = NormalizeColumnRule(null_tokens=("", "NA", "N/A"))
        self.assertEqual(r.null_tokens, ("", "NA", "N/A"))

    def test_case_sensitive_null_tokens(self) -> None:
        r = NormalizeColumnRule(
            null_tokens=("NULL",),
            null_tokens_case_sensitive=True,
        )
        self.assertTrue(r.null_tokens_case_sensitive)

    def test_strip_whitespace_flag(self) -> None:
        r = NormalizeColumnRule(strip_whitespace=True)
        self.assertTrue(r.strip_whitespace)

    def test_frozen(self) -> None:
        r = NormalizeColumnRule()
        with self.assertRaises((AttributeError, TypeError)):
            r.case = "lower"  # type: ignore[misc]
