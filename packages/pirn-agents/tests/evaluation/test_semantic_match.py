"""Tests for :func:`semantic_match` with a stub embedder."""

from __future__ import annotations

import unittest
from collections.abc import Sequence

from pirn_agents.evaluation.semantic_match import semantic_match


def _bag_of_words_embedder(vocab: Sequence[str]):
    """Return a deterministic, backend-free embedder over a fixed vocabulary.

    Each string maps to a term-presence vector, so lexical overlap drives the
    cosine similarity without importing any embedding backend.
    """

    def _embed(text: str) -> list[float]:
        tokens = set(text.lower().split())
        return [1.0 if word in tokens else 0.0 for word in vocab]

    return _embed


class SemanticMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.embed = _bag_of_words_embedder(["paris", "france", "capital", "city", "of"])

    def test_identical_text_scores_one_and_passes(self) -> None:
        result = semantic_match("Paris France", "Paris France", embedder=self.embed)
        assert result.name == "semantic_match"
        assert round(result.score, 9) == 1.0
        assert result.detail["passed"] is True

    def test_partial_overlap_scores_between_zero_and_one(self) -> None:
        result = semantic_match(
            "capital city of France", "France", embedder=self.embed, threshold=0.9
        )
        assert 0.0 < result.score < 1.0
        assert result.detail["passed"] is False

    def test_no_overlap_scores_zero(self) -> None:
        result = semantic_match("paris", "capital", embedder=self.embed)
        assert result.score == 0.0

    def test_threshold_controls_pass_flag(self) -> None:
        low = semantic_match("France", "capital city of France", embedder=self.embed, threshold=0.1)
        assert low.detail["passed"] is True

    def test_non_callable_embedder_raises(self) -> None:
        with self.assertRaises(TypeError):
            semantic_match("a", "b", embedder="not-callable")  # type: ignore[arg-type]

    def test_non_str_prediction_raises(self) -> None:
        with self.assertRaises(TypeError):
            semantic_match(1, "b", embedder=self.embed)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
