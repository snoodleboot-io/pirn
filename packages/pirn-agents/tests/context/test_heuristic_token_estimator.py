"""Unit tests for :class:`HeuristicTokenEstimator`."""

from __future__ import annotations

import unittest

from pirn_agents.context.heuristic_token_estimator import HeuristicTokenEstimator


class TestEstimate(unittest.TestCase):
    def test_empty_text_is_zero(self) -> None:
        assert HeuristicTokenEstimator().estimate("") == 0

    def test_default_ratio_is_four_chars_per_token(self) -> None:
        # 8 chars / 4 == 2 tokens.
        assert HeuristicTokenEstimator().estimate("abcdefgh") == 2

    def test_rounds_up(self) -> None:
        # 9 chars / 4 -> ceil(2.25) == 3.
        assert HeuristicTokenEstimator().estimate("abcdefghi") == 3

    def test_short_text_is_at_least_one_token(self) -> None:
        assert HeuristicTokenEstimator().estimate("a") == 1

    def test_provider_specific_ratio(self) -> None:
        est = HeuristicTokenEstimator(name="provider-x", chars_per_token=2.0)
        assert est.name == "provider-x"
        assert est.estimate("abcd") == 2


class TestValidation(unittest.TestCase):
    def test_rejects_non_positive_ratio(self) -> None:
        with self.assertRaisesRegex(ValueError, "chars_per_token"):
            HeuristicTokenEstimator(chars_per_token=0)

    def test_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "name"):
            HeuristicTokenEstimator(name="")

    def test_rejects_non_str_text(self) -> None:
        with self.assertRaisesRegex(TypeError, "text"):
            HeuristicTokenEstimator().estimate(123)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
