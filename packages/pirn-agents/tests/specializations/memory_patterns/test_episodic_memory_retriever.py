"""Tests for :class:`EpisodicMemoryRetriever`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.memory_patterns.episodic_memory_retriever import (
    EpisodicMemoryRetriever,
)
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubMemoryStore


def _make_knot() -> EpisodicMemoryRetriever:
    with Tapestry():
        return EpisodicMemoryRetriever(
            context="ctx",
            store=StubMemoryStore([]),
            _config=KnotConfig(id="ret"),
        )


class TestEpisodicMemoryRetrieverProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_matching_memories(self) -> None:
        k = _make_knot()
        hits = [
            {"session_id": "s1", "messages": ["hello"]},
            {"session_id": "s2", "messages": ["world"]},
        ]
        store = StubMemoryStore(hits)
        memories = await k.process(context="hello world", store=store, top_k=2)
        assert len(memories) == 2
        assert store.search_queries == ["hello world"]

    async def test_respects_top_k_limit(self) -> None:
        k = _make_knot()
        hits = [{"id": i} for i in range(5)]
        store = StubMemoryStore(hits)
        memories = await k.process(context="query", store=store, top_k=3)
        assert len(memories) == 3

    async def test_returns_empty_when_no_hits(self) -> None:
        k = _make_knot()
        store = StubMemoryStore([])
        memories = await k.process(context="nothing here", store=store, top_k=5)
        assert memories == []

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(context="ctx", store="bad", top_k=5)  # type: ignore[arg-type]

    async def test_rejects_zero_top_k(self) -> None:
        k = _make_knot()
        store = StubMemoryStore([])
        with self.assertRaises(ValueError):
            await k.process(context="ctx", store=store, top_k=0)
