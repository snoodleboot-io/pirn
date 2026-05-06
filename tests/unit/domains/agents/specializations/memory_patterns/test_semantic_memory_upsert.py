"""Tests for :class:`SemanticMemoryUpsert`."""

from __future__ import annotations

import hashlib
import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.semantic_memory_upsert import (
    SemanticMemoryUpsert,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class RecordingMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.data: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.data[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.data.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            if False:
                yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self.data.pop(key, None)

    async def close(self) -> None:
        return None


def _make_knot() -> SemanticMemoryUpsert:
    with Tapestry():
        return SemanticMemoryUpsert(
            response=AgentResponse(content="x"),
            llm=StubLLMProvider(["fact1"]),
            store=RecordingMemoryStore(),
            _config=KnotConfig(id="upsert"),
        )


class TestSemanticMemoryUpsertProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_and_stores_facts(self) -> None:
        k = _make_knot()
        store = RecordingMemoryStore()
        llm = StubLLMProvider(["- Paris is the capital of France\n- The Eiffel Tower is in Paris"])
        response = AgentResponse(content="Paris is the capital of France.")
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 2
        assert len(store.data) == 2

    async def test_deduplicates_existing_facts(self) -> None:
        k = _make_knot()
        store = RecordingMemoryStore()
        llm = StubLLMProvider(["existing fact"])
        response = AgentResponse(content="existing fact")
        key = "fact:" + hashlib.sha256(b"existing fact").hexdigest()[:16]
        await store.store(key, {"fact": "existing fact"})
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 0

    async def test_returns_zero_for_empty_response(self) -> None:
        k = _make_knot()
        store = RecordingMemoryStore()
        llm = StubLLMProvider([""])
        response = AgentResponse(content="")
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 0

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        store = RecordingMemoryStore()
        with self.assertRaises(TypeError):
            await k.process(response=AgentResponse(content="x"), llm="bad", store=store)  # type: ignore[arg-type]

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["fact1"])
        with self.assertRaises(TypeError):
            await k.process(response=AgentResponse(content="x"), llm=llm, store="bad")  # type: ignore[arg-type]
