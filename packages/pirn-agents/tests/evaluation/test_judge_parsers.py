"""Tests for the judge free-text parsers (S4)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.judge_score_parser import JudgeScoreParser
from pirn_agents.evaluation.pairwise_choice_parser import PairwiseChoiceParser


class ParseJudgeScoreTests(unittest.TestCase):
    def test_reads_unit_interval_number(self) -> None:
        assert JudgeScoreParser().parse("0.8") == 0.8

    def test_reads_leading_number_in_sentence(self) -> None:
        assert JudgeScoreParser().parse("Score: 0.5 because ...") == 0.5

    def test_scales_zero_to_ten_rating(self) -> None:
        assert JudgeScoreParser().parse("7 out of 10") == 0.7

    def test_clamps_large_number(self) -> None:
        assert JudgeScoreParser().parse("100") == 1.0

    def test_negative_clamps_to_zero(self) -> None:
        assert JudgeScoreParser().parse("-0.5") == 0.0

    def test_no_number_fails_closed(self) -> None:
        assert JudgeScoreParser().parse("excellent") == 0.0

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            JudgeScoreParser().parse(1)  # type: ignore[arg-type]


class ParsePairwiseChoiceTests(unittest.TestCase):
    def test_leading_a(self) -> None:
        assert PairwiseChoiceParser().parse("A is better") == "a"

    def test_leading_b(self) -> None:
        assert PairwiseChoiceParser().parse("B, clearly") == "b"

    def test_tie(self) -> None:
        assert PairwiseChoiceParser().parse("It's a tie") == "tie"

    def test_equal_reads_tie(self) -> None:
        assert PairwiseChoiceParser().parse("both are equal") == "tie"

    def test_empty_reads_tie(self) -> None:
        assert PairwiseChoiceParser().parse("") == "tie"

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            PairwiseChoiceParser().parse(1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
