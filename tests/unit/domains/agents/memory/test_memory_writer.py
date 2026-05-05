"""Unit tests for :class:`MemoryWriter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory.memory_writer import MemoryWriter
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubMemoryStore


@knot
async def emit_key() -> str:
    return "alpha"


@knot
async def emit_value() -> dict[str, int]:
    return {"v": 1}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_writes_and_returns_key(self) -> None:
        store = StubMemoryStore()
        with Tapestry() as t:
            k = emit_key(_config=KnotConfig(id="k"))
            v = emit_value(_config=KnotConfig(id="v"))
            MemoryWriter(key=k, value=v, store=store, _config=KnotConfig(id="w"))
        result = await t.run(RunRequest())
        assert result.outputs["w"] == "alpha"
        assert await store.retrieve("alpha") == {"v": 1}

    async def test_rejects_empty_key(self) -> None:
        @knot
        async def bad_key() -> str:
            return ""

        store = StubMemoryStore()
        with Tapestry() as t:
            k = bad_key(_config=KnotConfig(id="k"))
            v = emit_value(_config=KnotConfig(id="v"))
            MemoryWriter(key=k, value=v, store=store, _config=KnotConfig(id="w"))
        result = await t.run(RunRequest())
        assert "w" not in result.outputs


class TestConstruction(unittest.TestCase):
    def test_requires_memory_store(self) -> None:
        @knot
        async def k() -> str:
            return "k"

        @knot
        async def v() -> dict:
            return {}

        with Tapestry():
            kk = k(_config=KnotConfig(id="k"))
            vv = v(_config=KnotConfig(id="v"))
            with self.assertRaisesRegex(TypeError, "MemoryStore"):
                MemoryWriter(
                    key=kk,
                    value=vv,
                    store="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="w"),
                )
