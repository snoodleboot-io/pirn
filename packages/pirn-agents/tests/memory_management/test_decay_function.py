"""Unit tests for :func:`decay_score`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.decay_function import decay_score


class TestDecayScore(unittest.TestCase):
    def test_zero_age_returns_full_importance(self) -> None:
        assert decay_score(0.8, 0.0, 100.0) == 0.8

    def test_one_half_life_halves_value(self) -> None:
        assert decay_score(1.0, 100.0, 100.0) == 0.5

    def test_two_half_lives_quarter_value(self) -> None:
        assert decay_score(1.0, 200.0, 100.0) == 0.25

    def test_negative_age_clamped_to_zero(self) -> None:
        assert decay_score(0.6, -50.0, 100.0) == 0.6

    def test_rejects_non_positive_half_life(self) -> None:
        with self.assertRaises(ValueError):
            decay_score(1.0, 10.0, 0.0)
