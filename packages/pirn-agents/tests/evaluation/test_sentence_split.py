"""Tests for :class:`SentenceSplitter` and :class:`BinaryVerdictParser`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.binary_verdict_parser import BinaryVerdictParser
from pirn_agents.evaluation.sentence_splitter import SentenceSplitter


class SplitSentencesTests(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self) -> None:
        assert SentenceSplitter().split("A is true. B is false! Is C?") == [
            "A is true",
            "B is false",
            "Is C",
        ]

    def test_empty_text_yields_no_sentences(self) -> None:
        assert SentenceSplitter().split("   ") == []

    def test_single_clause_without_punctuation(self) -> None:
        assert SentenceSplitter().split("just one claim") == ["just one claim"]

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            SentenceSplitter().split(None)  # type: ignore[arg-type]


class ParseBinaryVerdictTests(unittest.TestCase):
    def test_leading_yes_is_true(self) -> None:
        assert BinaryVerdictParser().parse("Yes, clearly supported.") is True

    def test_leading_no_is_false(self) -> None:
        assert BinaryVerdictParser().parse("No — not in the context.") is False

    def test_not_supported_reads_false(self) -> None:
        assert BinaryVerdictParser().parse("This is not supported by the passage") is False

    def test_supported_reads_true(self) -> None:
        assert BinaryVerdictParser().parse("The claim is supported") is True

    def test_empty_fails_closed(self) -> None:
        assert BinaryVerdictParser().parse("") is False

    def test_unrecognized_fails_closed(self) -> None:
        assert BinaryVerdictParser().parse("maybe, hard to say") is False

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            BinaryVerdictParser().parse(1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
