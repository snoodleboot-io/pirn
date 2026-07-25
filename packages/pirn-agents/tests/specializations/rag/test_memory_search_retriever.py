"""Unit tests for :class:`MemorySearchRetriever`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from tests.specializations.conftest import StubMemoryStore


class TestMemorySearchRetrieverConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_memory_store(self) -> None:
        with Tapestry():
            k = MemorySearchRetriever.__new__(MemorySearchRetriever)
            object.__setattr__(k, "_config", KnotConfig(id="msr"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(store="bad", query="q")  # type: ignore[arg-type]

    async def test_rejects_non_positive_top_k(self) -> None:
        store = StubMemoryStore(hits=[])
        with Tapestry():
            k = MemorySearchRetriever.__new__(MemorySearchRetriever)
            object.__setattr__(k, "_config", KnotConfig(id="msr"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(store=store, query="q", top_k=0)


class TestMemorySearchRetrieverProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_hits_from_store(self) -> None:
        hits = [{"text": "hit 1"}, {"text": "hit 2"}]
        store = StubMemoryStore(hits=hits)
        with Tapestry() as t:
            MemorySearchRetriever(
                store=store,
                query="question",
                top_k=5,
                _config=KnotConfig(id="msr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["msr"]
        assert len(out) == 2

    async def test_caps_results_at_top_k(self) -> None:
        hits = [{"text": f"hit {i}"} for i in range(10)]
        store = StubMemoryStore(hits=hits)
        with Tapestry() as t:
            MemorySearchRetriever(
                store=store,
                query="q",
                top_k=3,
                _config=KnotConfig(id="msr"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["msr"]) == 3

    async def test_rejects_non_string_query(self) -> None:
        store = StubMemoryStore(hits=[])
        with Tapestry():
            with self.assertRaises(TypeError):
                MemorySearchRetriever(
                    store=store,
                    query=42,  # type: ignore[arg-type]
                    top_k=5,
                    _config=KnotConfig(id="msr"),
                )
