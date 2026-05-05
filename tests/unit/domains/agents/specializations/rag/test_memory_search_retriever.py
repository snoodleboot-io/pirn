"""Unit tests for :class:`MemorySearchRetriever`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


class TestMemorySearchRetrieverConstruction(unittest.TestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                MemorySearchRetriever(
                    store="bad",  # type: ignore[arg-type]
                    query="q",
                    _config=KnotConfig(id="msr"),
                )

    def test_rejects_non_positive_top_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k"):
            with Tapestry():
                MemorySearchRetriever(
                    store=StubMemoryStore(hits=[]),
                    query="q",
                    top_k=0,
                    _config=KnotConfig(id="msr"),
                )


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
