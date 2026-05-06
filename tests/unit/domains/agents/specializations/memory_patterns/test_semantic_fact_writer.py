"""Unit tests for :class:`SemanticFactWriter`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.memory_patterns.semantic_fact_writer import (
    SemanticFactWriter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


class _TrackingStore(StubMemoryStore):
    def __init__(self):
        super().__init__(hits=[])
        self.stored: dict[str, Any] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored[key] = dict(value)


def _make_knot() -> SemanticFactWriter:
    with Tapestry():
        return SemanticFactWriter(
            facts=[],
            store=_TrackingStore(),
            _config=KnotConfig(id="sfw"),
        )


class TestSemanticFactWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_count_of_stored_facts(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        count = await k.process(facts=["fact one", "fact two", "fact three"], store=store)
        assert count == 3

    async def test_stores_under_semantic_key(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        await k.process(facts=["water is wet"], store=store)
        keys = list(store.stored.keys())
        assert all(key.startswith("semantic:") for key in keys)

    async def test_empty_facts_returns_zero(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        count = await k.process(facts=[], store=store)
        assert count == 0

    async def test_rejects_non_string_fact(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(TypeError):
            await k.process(facts=[42], store=store)  # type: ignore[list-item]

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(facts=[], store="bad")  # type: ignore[arg-type]
