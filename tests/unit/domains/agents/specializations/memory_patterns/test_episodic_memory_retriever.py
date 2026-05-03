"""Tests for :class:`EpisodicMemoryRetriever`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.memory_patterns.episodic_memory_retriever import (
    EpisodicMemoryRetriever,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


@pytest.mark.asyncio
class TestEpisodicMemoryRetrieverConstruction:
    async def test_rejects_non_memory_store(self) -> None:
        with pytest.raises(TypeError, match="store must be a MemoryStore"):
            with Tapestry():
                EpisodicMemoryRetriever(
                    context="ctx",
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ret"),
                )

    async def test_rejects_zero_top_k(self) -> None:
        store = StubMemoryStore([])
        with pytest.raises(ValueError, match="top_k must be a positive int"):
            with Tapestry():
                EpisodicMemoryRetriever(
                    context="ctx",
                    store=store,
                    top_k=0,
                    _config=KnotConfig(id="ret"),
                )


@pytest.mark.asyncio
class TestEpisodicMemoryRetrieverHappyPath:
    async def test_returns_matching_memories(self) -> None:
        hits = [
            {"session_id": "s1", "messages": ["hello"]},
            {"session_id": "s2", "messages": ["world"]},
        ]
        store = StubMemoryStore(hits)
        with Tapestry() as t:
            EpisodicMemoryRetriever(
                context="hello world",
                store=store,
                top_k=2,
                _config=KnotConfig(id="ret"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        memories = result.outputs["ret"]
        assert len(memories) == 2
        assert store.search_queries == ["hello world"]

    async def test_respects_top_k_limit(self) -> None:
        hits = [{"id": i} for i in range(5)]
        store = StubMemoryStore(hits)
        with Tapestry() as t:
            EpisodicMemoryRetriever(
                context="query",
                store=store,
                top_k=3,
                _config=KnotConfig(id="ret"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        memories = result.outputs["ret"]
        assert len(memories) == 3

    async def test_returns_empty_when_no_hits(self) -> None:
        store = StubMemoryStore([])
        with Tapestry() as t:
            EpisodicMemoryRetriever(
                context="nothing here",
                store=store,
                _config=KnotConfig(id="ret"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ret"] == []
