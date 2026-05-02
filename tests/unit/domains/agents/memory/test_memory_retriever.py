"""Unit tests for :class:`MemoryRetriever`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory.memory_retriever import MemoryRetriever
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubMemoryStore


@knot
async def emit_key() -> str:
    return "alpha"


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_value_for_existing_key(self) -> None:
        store = StubMemoryStore()
        await store.store("alpha", {"v": 1})
        with Tapestry() as t:
            k = emit_key(_config=KnotConfig(id="k"))
            MemoryRetriever(key=k, store=store, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        assert dict(result.outputs["r"]) == {"v": 1}

    async def test_raises_key_error_when_missing(self) -> None:
        store = StubMemoryStore()
        with Tapestry() as t:
            k = emit_key(_config=KnotConfig(id="k"))
            MemoryRetriever(key=k, store=store, _config=KnotConfig(id="r"))
        result = await t.run(RunRequest())
        assert "r" not in result.outputs


class TestConstruction:
    def test_requires_memory_store(self) -> None:
        @knot
        async def k() -> str:
            return "k"

        with Tapestry():
            kk = k(_config=KnotConfig(id="k"))
            with pytest.raises(TypeError, match="MemoryStore"):
                MemoryRetriever(
                    key=kk,
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="r"),
                )
