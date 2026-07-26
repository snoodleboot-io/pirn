"""Unit tests for :class:`ScoreAggregator` (S3)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.score_aggregator import ScoreAggregator


class MeanTests(unittest.TestCase):
    def test_mean_of_samples(self) -> None:
        assert ScoreAggregator().mean([1.0, 0.0]) == 0.5

    def test_mean_single_sample(self) -> None:
        assert ScoreAggregator().mean([0.8]) == 0.8


class WeightedMeanTests(unittest.TestCase):
    def test_weighted_overall(self) -> None:
        # correctness=1.0 (weight 3), style=0.0 (weight 1) => 3/4 = 0.75
        assert ScoreAggregator().weighted_mean([1.0, 0.0], [3.0, 1.0]) == 0.75

    def test_equal_weights_is_plain_mean(self) -> None:
        assert ScoreAggregator().weighted_mean([1.0, 0.0], [1.0, 1.0]) == 0.5


class FractionTests(unittest.TestCase):
    def test_fraction_of_total(self) -> None:
        assert round(ScoreAggregator().fraction(2, 3), 4) == round(2 / 3, 4)

    def test_zero_total_is_zero(self) -> None:
        assert ScoreAggregator().fraction(0, 0) == 0.0


class MajorityTests(unittest.TestCase):
    def test_a_majority(self) -> None:
        assert ScoreAggregator().majority(2, 1) == "a"

    def test_b_majority(self) -> None:
        assert ScoreAggregator().majority(1, 2) == "b"

    def test_equal_is_tie(self) -> None:
        assert ScoreAggregator().majority(1, 1) == "tie"


class OrdersConsistentTests(unittest.TestCase):
    def test_agreeing_orders(self) -> None:
        assert ScoreAggregator().orders_consistent(["a", "a"]) is True

    def test_disagreeing_orders(self) -> None:
        assert ScoreAggregator().orders_consistent(["a", "b"]) is False


class ResolveWinnerTests(unittest.TestCase):
    def test_majority_wins_without_swap(self) -> None:
        winner = ScoreAggregator().resolve_winner(
            votes_a=2, votes_b=1, position_swap=False, consistent=True
        )
        assert winner == "a"

    def test_inconsistent_swap_forces_tie(self) -> None:
        winner = ScoreAggregator().resolve_winner(
            votes_a=2, votes_b=0, position_swap=True, consistent=False
        )
        assert winner == "tie"

    def test_consistent_swap_keeps_majority(self) -> None:
        winner = ScoreAggregator().resolve_winner(
            votes_a=0, votes_b=2, position_swap=True, consistent=True
        )
        assert winner == "b"


if __name__ == "__main__":
    unittest.main()
