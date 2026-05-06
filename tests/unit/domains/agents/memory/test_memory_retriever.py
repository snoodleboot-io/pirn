"""Unit tests for :class:`MemoryRetriever`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.memory.memory_retriever import MemoryRetriever
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubMemoryStore


def _make_knot(store: StubMemoryStore) -> MemoryRetriever:
    @knot
    async def _k() -> str:
        return "key"

    with Tapestry():
        upstream = _k(_config=KnotConfig(id="k"))
        return MemoryRetriever(key=upstream, store=store, _config=KnotConfig(id="r"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_value_for_existing_key(self) -> None:
        store = StubMemoryStore()
        await store.store("alpha", {"v": 1})
        k = _make_knot(store)
        result = await k.process(key="alpha", store=store)
        assert dict(result) == {"v": 1}

    async def test_raises_key_error_when_missing(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(KeyError):
            await k.process(key="alpha", store=store)

    async def test_rejects_empty_key(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(ValueError):
            await k.process(key="", store=store)

    async def test_rejects_non_memory_store(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            await k.process(
                key="alpha",
                store="bad",  # type: ignore[arg-type]
            )
