"""Tests for :class:`IterativeRetriever`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.iterative_retriever import IterativeRetriever
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class _PerQueryStore(MemoryStore):
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


def _retriever() -> IterativeRetriever:
    with Tapestry():
        knot = IterativeRetriever.__new__(IterativeRetriever)
        object.__setattr__(knot, "_config", KnotConfig(id="iterate"))
    return knot


class TestIterativeRetriever(unittest.IsolatedAsyncioTestCase):
    async def test_refines_then_stops_on_done(self) -> None:
        store = _PerQueryStore(
            {"start": [{"id": "1", "text": "a"}], "next": [{"id": "2", "text": "b"}]}
        )
        llm = StubLLMProvider(["REFINE: next", "DONE"])
        knot = _retriever()
        docs = await knot.process(query="start", memory=store, llm=llm, max_iterations=3, top_k=1)
        assert store.search_queries == ["start", "next"]
        assert sorted(d["id"] for d in docs) == ["1", "2"]

    async def test_stops_immediately_on_done(self) -> None:
        store = _PerQueryStore({"start": [{"id": "1"}]})
        llm = StubLLMProvider(["DONE"])
        knot = _retriever()
        docs = await knot.process(query="start", memory=store, llm=llm, max_iterations=3, top_k=1)
        assert store.search_queries == ["start"]
        assert len(docs) == 1

    async def test_bounded_by_max_iterations(self) -> None:
        store = _PerQueryStore({"start": [{"id": "1"}], "again": [{"id": "2"}]})
        # LLM always wants to refine, but the budget caps the loop at 2 rounds.
        llm = StubLLMProvider(["REFINE: again"])
        knot = _retriever()
        await knot.process(query="start", memory=store, llm=llm, max_iterations=2, top_k=1)
        assert store.search_queries == ["start", "again"]

    async def test_rejects_non_positive_iterations(self) -> None:
        knot = _retriever()
        with self.assertRaisesRegex(ValueError, "max_iterations must be a positive int"):
            await knot.process(
                query="q", memory=StubMemoryStore([]), llm=StubLLMProvider(["x"]), max_iterations=0
            )
