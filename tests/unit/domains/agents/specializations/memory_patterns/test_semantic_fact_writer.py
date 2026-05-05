"""Unit tests for :class:`SemanticFactWriter`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


class TestSemanticFactWriterConstruction(unittest.TestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                SemanticFactWriter(
                    facts=["fact"],
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="sfw"),
                )


class TestSemanticFactWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_count_of_stored_facts(self) -> None:
        store = _TrackingStore()
        with Tapestry() as t:
            SemanticFactWriter(
                facts=["fact one", "fact two", "fact three"],
                store=store,
                _config=KnotConfig(id="sfw"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sfw"] == 3

    async def test_stores_under_semantic_key(self) -> None:
        store = _TrackingStore()
        with Tapestry() as t:
            SemanticFactWriter(
                facts=["water is wet"],
                store=store,
                _config=KnotConfig(id="sfw"),
            )
        await t.run(RunRequest())
        keys = list(store.stored.keys())
        assert all(k.startswith("semantic:") for k in keys)

    async def test_empty_facts_returns_zero(self) -> None:
        store = _TrackingStore()
        with Tapestry() as t:
            SemanticFactWriter(
                facts=[],
                store=store,
                _config=KnotConfig(id="sfw"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sfw"] == 0

    async def test_rejects_non_string_fact(self) -> None:
        store = _TrackingStore()
        with Tapestry():
            with self.assertRaises(TypeError):
                SemanticFactWriter(
                    facts=[42],  # type: ignore[list-item]
                    store=store,
                    _config=KnotConfig(id="sfw"),
                )
