"""Unit tests for :class:`VectorMatch` invariants."""

from __future__ import annotations

import math
import unittest

from pirn_agents.vector_stores.vector_match import VectorMatch


class TestVectorMatch(unittest.TestCase):
    def test_valid_match_is_constructed(self) -> None:
        match = VectorMatch(id="k1", score=0.5, metadata={"k": "v"}, document="doc")
        assert (match.id, match.score, match.document) == ("k1", 0.5, "doc")

    def test_accepts_score_bounds(self) -> None:
        assert VectorMatch(id="a", score=-1.0).score == -1.0
        assert VectorMatch(id="b", score=1.0).score == 1.0

    def test_accepts_boundary_float_drift(self) -> None:
        # A self-match cosine similarity may round just past 1.0.
        assert VectorMatch(id="c", score=1.0 + 1e-9).score == 1.0 + 1e-9

    def test_accepts_unbounded_positive_score(self) -> None:
        # Range is metric-specific (dot-product stores are unbounded); the neutral
        # value object accepts any finite score above the cosine range.
        assert VectorMatch(id="a", score=1.5).score == 1.5
        assert VectorMatch(id="b", score=42.0).score == 42.0

    def test_accepts_unbounded_negative_score(self) -> None:
        # Negative similarities below the cosine floor are valid for other metrics.
        assert VectorMatch(id="a", score=-5.0).score == -5.0

    def test_rejects_empty_id(self) -> None:
        with self.assertRaises(TypeError):
            VectorMatch(id="", score=0.5)

    def test_rejects_nan_score(self) -> None:
        with self.assertRaises(ValueError):
            VectorMatch(id="a", score=math.nan)

    def test_rejects_positive_inf_score(self) -> None:
        with self.assertRaises(ValueError):
            VectorMatch(id="a", score=math.inf)

    def test_rejects_negative_inf_score(self) -> None:
        with self.assertRaises(ValueError):
            VectorMatch(id="a", score=-math.inf)

    def test_rejects_bool_score(self) -> None:
        with self.assertRaises(TypeError):
            VectorMatch(id="a", score=True)  # type: ignore[arg-type]

    def test_rejects_non_mapping_metadata(self) -> None:
        with self.assertRaises(TypeError):
            VectorMatch(id="a", score=0.5, metadata=["nope"])  # type: ignore[arg-type]

    def test_rejects_non_str_document(self) -> None:
        with self.assertRaises(TypeError):
            VectorMatch(id="a", score=0.5, document=123)  # type: ignore[arg-type]
