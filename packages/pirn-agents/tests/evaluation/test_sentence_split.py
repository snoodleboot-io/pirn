"""Tests for :func:`split_sentences` and :func:`parse_binary_verdict`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.binary_verdict import parse_binary_verdict
from pirn_agents.evaluation.sentence_split import split_sentences


class SplitSentencesTests(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self) -> None:
        assert split_sentences("A is true. B is false! Is C?") == [
            "A is true",
            "B is false",
            "Is C",
        ]

    def test_empty_text_yields_no_sentences(self) -> None:
        assert split_sentences("   ") == []

    def test_single_clause_without_punctuation(self) -> None:
        assert split_sentences("just one claim") == ["just one claim"]

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            split_sentences(None)  # type: ignore[arg-type]


class ParseBinaryVerdictTests(unittest.TestCase):
    def test_leading_yes_is_true(self) -> None:
        assert parse_binary_verdict("Yes, clearly supported.") is True

    def test_leading_no_is_false(self) -> None:
        assert parse_binary_verdict("No — not in the context.") is False

    def test_not_supported_reads_false(self) -> None:
        assert parse_binary_verdict("This is not supported by the passage") is False

    def test_supported_reads_true(self) -> None:
        assert parse_binary_verdict("The claim is supported") is True

    def test_empty_fails_closed(self) -> None:
        assert parse_binary_verdict("") is False

    def test_unrecognized_fails_closed(self) -> None:
        assert parse_binary_verdict("maybe, hard to say") is False

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            parse_binary_verdict(1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
