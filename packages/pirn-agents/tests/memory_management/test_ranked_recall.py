"""Unit tests for :class:`RankedRecall`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.ranked_recall import RankedRecall
from pirn_agents.memory_management.recall_candidate import RecallCandidate
from pirn_agents.memory_management.recall_weights import RecallWeights
from tests.memory_management.conftest import StubReranker, make_record

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _make_knot() -> RankedRecall:
    with Tapestry():
        return RankedRecall(query="q", candidates=[], now=_NOW, _config=KnotConfig(id="rr"))


def _candidates() -> list[RecallCandidate]:
    # Same created_at -> recency signal is constant (normalises to 0), so
    # ordering is driven by relevance/importance under the chosen weights.
    high_rel = make_record(id="high_rel", importance=0.1, created_at=_NOW)
    high_imp = make_record(id="high_imp", importance=0.9, created_at=_NOW)
    return [
        RecallCandidate(record=high_rel, relevance=0.9),
        RecallCandidate(record=high_imp, relevance=0.1),
    ]


class TestRankedRecall(unittest.IsolatedAsyncioTestCase):
    async def test_empty_candidates_returns_empty(self) -> None:
        knot = _make_knot()
        assert await knot.process(query="q", candidates=[], now=_NOW) == []

    async def test_relevance_weight_orders_by_relevance(self) -> None:
        knot = _make_knot()
        ranked = await knot.process(
            query="q",
            candidates=_candidates(),
            now=_NOW,
            weights=RecallWeights(relevance=1.0, recency=0.0, importance=0.0),
        )
        assert [r.record.id for r in ranked] == ["high_rel", "high_imp"]

    async def test_importance_weight_orders_by_importance(self) -> None:
        knot = _make_knot()
        ranked = await knot.process(
            query="q",
            candidates=_candidates(),
            now=_NOW,
            weights=RecallWeights(relevance=0.0, recency=0.0, importance=1.0),
        )
        assert [r.record.id for r in ranked] == ["high_imp", "high_rel"]

    async def test_recency_weight_orders_by_recency(self) -> None:
        knot = _make_knot()
        recent = make_record(id="recent", importance=0.0, created_at=_NOW)
        stale = make_record(id="stale", importance=0.0, created_at=datetime(2025, 1, 1, tzinfo=UTC))
        candidates = [
            RecallCandidate(record=stale, relevance=0.0),
            RecallCandidate(record=recent, relevance=0.0),
        ]
        ranked = await knot.process(
            query="q",
            candidates=candidates,
            now=_NOW,
            weights=RecallWeights(relevance=0.0, recency=1.0, importance=0.0),
        )
        assert ranked[0].record.id == "recent"

    async def test_components_are_normalised_into_unit_range(self) -> None:
        knot = _make_knot()
        ranked = await knot.process(query="q", candidates=_candidates(), now=_NOW)
        for item in ranked:
            assert 0.0 <= item.relevance <= 1.0
            assert 0.0 <= item.importance <= 1.0

    async def test_rerank_hook_overrides_relevance(self) -> None:
        knot = _make_knot()
        # Reranker flips relevance: the low-raw-relevance record scores highest.
        reranker = StubReranker({"high_rel": 0.0, "high_imp": 1.0})
        ranked = await knot.process(
            query="q",
            candidates=_candidates(),
            now=_NOW,
            weights=RecallWeights(relevance=1.0, recency=0.0, importance=0.0),
            reranker=reranker,
        )
        assert [r.record.id for r in ranked] == ["high_imp", "high_rel"]
        assert reranker.calls == ["q"]

    async def test_default_weights_are_provider_neutral_equal_blend(self) -> None:
        knot = _make_knot()
        ranked = await knot.process(query="q", candidates=_candidates(), now=_NOW)
        assert {r.record.id for r in ranked} == {"high_rel", "high_imp"}

    async def test_rejects_non_candidate(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(query="q", candidates=["bad"], now=_NOW)  # type: ignore[list-item]

    async def test_rejects_non_weights(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                query="q",
                candidates=_candidates(),
                now=_NOW,
                weights="bad",  # type: ignore[arg-type]
            )

    async def test_rejects_non_reranker(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                query="q",
                candidates=_candidates(),
                now=_NOW,
                reranker=object(),  # type: ignore[arg-type]
            )
