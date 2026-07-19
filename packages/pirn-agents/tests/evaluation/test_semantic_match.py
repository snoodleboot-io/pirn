"""Tests for :class:`SemanticMatch` with a stub embedder."""

from __future__ import annotations

import unittest
from collections.abc import Sequence

from pirn_agents.evaluation.semantic_match import SemanticMatch


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
        result = SemanticMatch(embedder=self.embed).score("Paris France", "Paris France")
        assert result.name == "semantic_match"
        assert round(result.score, 9) == 1.0
        assert result.detail["passed"] is True

    def test_partial_overlap_scores_between_zero_and_one(self) -> None:
        result = SemanticMatch(embedder=self.embed, threshold=0.9).score(
            "capital city of France", "France"
        )
        assert 0.0 < result.score < 1.0
        assert result.detail["passed"] is False

    def test_no_overlap_scores_zero(self) -> None:
        result = SemanticMatch(embedder=self.embed).score("paris", "capital")
        assert result.score == 0.0

    def test_threshold_controls_pass_flag(self) -> None:
        low = SemanticMatch(embedder=self.embed, threshold=0.1).score(
            "France", "capital city of France"
        )
        assert low.detail["passed"] is True

    def test_non_callable_embedder_raises(self) -> None:
        with self.assertRaises(TypeError):
            SemanticMatch(embedder="not-callable")  # type: ignore[arg-type]

    def test_non_str_prediction_raises(self) -> None:
        with self.assertRaises(TypeError):
            SemanticMatch(embedder=self.embed).score(1, "b")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
