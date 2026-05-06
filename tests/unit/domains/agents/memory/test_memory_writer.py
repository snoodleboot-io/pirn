"""Unit tests for :class:`MemoryWriter`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.memory.memory_writer import MemoryWriter
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubMemoryStore


def _make_knot(store: StubMemoryStore) -> MemoryWriter:
    @knot
    async def _k() -> str:
        return "k"

    @knot
    async def _v() -> dict:
        return {}

    with Tapestry():
        kk = _k(_config=KnotConfig(id="k"))
        vv = _v(_config=KnotConfig(id="v"))
        return MemoryWriter(key=kk, value=vv, store=store, _config=KnotConfig(id="w"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_writes_and_returns_key(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        result = await k.process(key="alpha", value={"v": 1}, store=store)
        assert result == "alpha"
        assert await store.retrieve("alpha") == {"v": 1}

    async def test_rejects_empty_key(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(ValueError):
            await k.process(key="", value={"v": 1}, store=store)

    async def test_rejects_non_mapping_value(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(TypeError):
            await k.process(
                key="alpha",
                value="not a mapping",  # type: ignore[arg-type]
                store=store,
            )

    async def test_rejects_non_memory_store(self) -> None:
        store = StubMemoryStore()
        k = _make_knot(store)
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            await k.process(
                key="alpha",
                value={"v": 1},
                store="not-a-store",  # type: ignore[arg-type]
            )
