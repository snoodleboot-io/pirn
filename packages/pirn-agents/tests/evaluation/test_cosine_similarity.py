"""Tests for :class:`CosineSimilarity`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.cosine_similarity import CosineSimilarity


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors_score_one(self) -> None:
        assert CosineSimilarity().compute([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0

    def test_orthogonal_vectors_score_zero(self) -> None:
        assert CosineSimilarity().compute([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_opposite_vectors_score_minus_one(self) -> None:
        assert CosineSimilarity().compute([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_zero_vector_yields_zero(self) -> None:
        assert CosineSimilarity().compute([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_length_mismatch_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            CosineSimilarity().compute([1.0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
