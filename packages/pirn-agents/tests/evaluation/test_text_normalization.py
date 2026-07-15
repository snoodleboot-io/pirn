"""Tests for :func:`normalize_text`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.text_normalization import normalize_text


class NormalizeTextTests(unittest.TestCase):
    def test_lowercases_and_strips_and_collapses_by_default(self) -> None:
        assert normalize_text("  Hello   World \n") == "hello world"

    def test_lower_can_be_disabled(self) -> None:
        assert normalize_text("Hello", lower=False) == "Hello"

    def test_collapse_whitespace_can_be_disabled(self) -> None:
        # Without collapsing, internal double spaces are preserved (strip still runs).
        assert normalize_text("a  b", collapse_whitespace=False, lower=False) == "a  b"

    def test_strip_can_be_disabled_without_collapse(self) -> None:
        assert normalize_text("  x  ", collapse_whitespace=False, strip=False, lower=False) == (
            "  x  "
        )

    def test_empty_string_stays_empty(self) -> None:
        assert normalize_text("   ") == ""

    def test_non_str_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            normalize_text(42)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
