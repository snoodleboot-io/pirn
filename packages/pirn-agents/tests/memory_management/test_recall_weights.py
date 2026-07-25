"""Unit tests for :class:`RecallWeights`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.recall_weights import RecallWeights


class TestRecallWeights(unittest.TestCase):
    def test_defaults_are_equal(self) -> None:
        weights = RecallWeights()
        assert (weights.relevance, weights.recency, weights.importance) == (1.0, 1.0, 1.0)

    def test_rejects_negative_weight(self) -> None:
        with self.assertRaises(ValueError):
            RecallWeights(relevance=-1.0)

    def test_rejects_bool_weight(self) -> None:
        with self.assertRaises(TypeError):
            RecallWeights(recency=True)  # type: ignore[arg-type]
