"""Tests for :class:`FusionRetriever`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.fusion_retriever import FusionRetriever
from tests.specializations.conftest import StubMemoryStore


class _PerQueryStore(MemoryStore):
    """Returns a distinct ranked hit list per query."""

    def __init__(self, mapping: Mapping[str, list[Mapping[str, Any]]]) -> None:
        self._mapping = {k: [dict(h) for h in v] for k, v in mapping.items()}
        self.search_queries: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        self.search_queries.append(query)
        hits = self._mapping.get(query, [])

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            for hit in hits[:top_k]:
                yield hit

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


def _retriever() -> FusionRetriever:
    with Tapestry():
        knot = FusionRetriever.__new__(FusionRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="fuse"))
    return knot


class TestFusionRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_fuses_and_dedupes_across_queries(self) -> None:
        store = _PerQueryStore(
            {
                "a": [{"id": "1", "text": "shared"}, {"id": "2", "text": "only-a"}],
                "b": [{"id": "1", "text": "shared"}, {"id": "3", "text": "only-b"}],
            }
        )
        knot = _retriever()
        results = await knot.process(queries=["a", "b"], store=store, top_k=5)
        ids = [r["id"] for r in results]
        # doc 1 is ranked first by both queries -> highest fused score, no dup.
        assert ids[0] == "1"
        assert sorted(ids) == ["1", "2", "3"]
        assert all("fusion_score" in r for r in results)

    async def test_respects_top_k(self) -> None:
        store = _PerQueryStore(
            {"a": [{"id": str(i)} for i in range(10)]},
        )
        knot = _retriever()
        results = await knot.process(queries=["a"], store=store, top_k=3)
        assert len(results) == 3

    async def test_empty_queries_returns_empty(self) -> None:
        knot = _retriever()
        results = await knot.process(queries=[], store=StubMemoryStore([]), top_k=5)
        assert results == []

    async def test_rejects_non_store(self) -> None:
        knot = _retriever()
        with self.assertRaisesRegex(TypeError, "store must be a MemoryStore"):
            await knot.process(queries=["a"], store="nope", top_k=5)  # type: ignore[arg-type]

    async def test_rejects_non_positive_top_k(self) -> None:
        knot = _retriever()
        with self.assertRaisesRegex(ValueError, "top_k must be a positive int"):
            await knot.process(queries=["a"], store=StubMemoryStore([]), top_k=0)
