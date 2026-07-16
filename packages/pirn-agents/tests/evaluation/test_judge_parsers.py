"""Tests for the judge free-text parsers (S4)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.parse_judge_score import parse_judge_score
from pirn_agents.evaluation.parse_pairwise_choice import parse_pairwise_choice


class ParseJudgeScoreTests(unittest.TestCase):
    def test_reads_unit_interval_number(self) -> None:
        assert parse_judge_score("0.8") == 0.8

    def test_reads_leading_number_in_sentence(self) -> None:
        assert parse_judge_score("Score: 0.5 because ...") == 0.5

    def test_scales_zero_to_ten_rating(self) -> None:
        assert parse_judge_score("7 out of 10") == 0.7

    def test_clamps_large_number(self) -> None:
        assert parse_judge_score("100") == 1.0

    def test_negative_clamps_to_zero(self) -> None:
        assert parse_judge_score("-0.5") == 0.0

    def test_no_number_fails_closed(self) -> None:
        assert parse_judge_score("excellent") == 0.0

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            parse_judge_score(1)  # type: ignore[arg-type]


class ParsePairwiseChoiceTests(unittest.TestCase):
    def test_leading_a(self) -> None:
        assert parse_pairwise_choice("A is better") == "a"

    def test_leading_b(self) -> None:
        assert parse_pairwise_choice("B, clearly") == "b"

    def test_tie(self) -> None:
        assert parse_pairwise_choice("It's a tie") == "tie"

    def test_equal_reads_tie(self) -> None:
        assert parse_pairwise_choice("both are equal") == "tie"

    def test_empty_reads_tie(self) -> None:
        assert parse_pairwise_choice("") == "tie"

    def test_non_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            parse_pairwise_choice(1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
