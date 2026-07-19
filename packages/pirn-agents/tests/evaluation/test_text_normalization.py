"""Tests for :class:`TextNormalizer`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.text_normalizer import TextNormalizer


class NormalizeTextTests(unittest.TestCase):
    def test_lowercases_and_strips_and_collapses_by_default(self) -> None:
        assert TextNormalizer().normalize("  Hello   World \n") == "hello world"

    def test_lower_can_be_disabled(self) -> None:
        assert TextNormalizer(lower=False).normalize("Hello") == "Hello"

    def test_collapse_whitespace_can_be_disabled(self) -> None:
        # Without collapsing, internal double spaces are preserved (strip still runs).
        assert TextNormalizer(collapse_whitespace=False, lower=False).normalize("a  b") == "a  b"

    def test_strip_can_be_disabled_without_collapse(self) -> None:
        assert TextNormalizer(collapse_whitespace=False, strip=False, lower=False).normalize(
            "  x  "
        ) == ("  x  ")

    def test_empty_string_stays_empty(self) -> None:
        assert TextNormalizer().normalize("   ") == ""

    def test_non_str_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            TextNormalizer().normalize(42)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
