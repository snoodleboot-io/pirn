"""Tests for :func:`exact_match`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.exact_match import exact_match


class ExactMatchTests(unittest.TestCase):
    def test_identical_strings_match(self) -> None:
        result = exact_match("Paris", "Paris")
        assert result.name == "exact_match"
        assert result.score == 1.0

    def test_case_and_whitespace_normalized_by_default(self) -> None:
        result = exact_match("  The   ANSWER ", "the answer")
        assert result.score == 1.0

    def test_normalization_can_be_disabled(self) -> None:
        result = exact_match("The Answer", "the answer", normalize=False)
        assert result.score == 0.0

    def test_partial_match_scores_zero(self) -> None:
        result = exact_match("Paris, France", "Paris")
        assert result.score == 0.0

    def test_two_empty_strings_match(self) -> None:
        assert exact_match("", "").score == 1.0

    def test_empty_prediction_against_nonempty_reference_fails(self) -> None:
        assert exact_match("", "answer").score == 0.0

    def test_non_str_prediction_raises(self) -> None:
        with self.assertRaises(TypeError):
            exact_match(1, "x")  # type: ignore[arg-type]

    def test_non_str_reference_raises(self) -> None:
        with self.assertRaises(TypeError):
            exact_match("x", 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
