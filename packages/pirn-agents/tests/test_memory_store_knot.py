"""Unit tests for :class:`MemoryStoreKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.memory_store_knot import MemoryStoreKnot
from tests.specializations.conftest import StubMemoryStore


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_store_unchanged(self) -> None:
        store = StubMemoryStore([])
        with Tapestry():
            k = MemoryStoreKnot.__new__(MemoryStoreKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(store=store)
        assert result is store
        assert isinstance(result, MemoryStore)
