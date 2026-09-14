"""Unit tests for :meth:`~pirn_agents.memory.management.decay_function.DecayFunction.score`."""

from __future__ import annotations

import unittest

from pirn_agents.memory.management.decay_function import DecayFunction


class TestDecayScore(unittest.TestCase):
    def test_zero_age_returns_full_importance(self) -> None:
        assert DecayFunction.score(0.8, 0.0, 100.0) == 0.8

    def test_one_half_life_halves_value(self) -> None:
        assert DecayFunction.score(1.0, 100.0, 100.0) == 0.5

    def test_two_half_lives_quarter_value(self) -> None:
        assert DecayFunction.score(1.0, 200.0, 100.0) == 0.25

    def test_negative_age_clamped_to_zero(self) -> None:
        assert DecayFunction.score(0.6, -50.0, 100.0) == 0.6

    def test_rejects_non_positive_half_life(self) -> None:
        with self.assertRaises(ValueError):
            DecayFunction.score(1.0, 10.0, 0.0)
