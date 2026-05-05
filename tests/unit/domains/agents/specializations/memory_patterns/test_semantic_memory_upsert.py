"""Tests for :class:`SemanticMemoryUpsert`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


class TestSemanticMemoryUpsertConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        store = RecordingMemoryStore()
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                SemanticMemoryUpsert(
                    response=AgentResponse(content="x"),
                    llm="bad",  # type: ignore[arg-type]
                    store=store,
                    _config=KnotConfig(id="upsert"),
                )

    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["fact1"])
        with self.assertRaisesRegex(TypeError, "store must be a MemoryStore"):
            with Tapestry():
                SemanticMemoryUpsert(
                    response=AgentResponse(content="x"),
                    llm=llm,
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="upsert"),
                )


class TestSemanticMemoryUpsertHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_and_stores_facts(self) -> None:
        store = RecordingMemoryStore()
        llm = StubLLMProvider(["- Paris is the capital of France\n- The Eiffel Tower is in Paris"])
        response = AgentResponse(content="Paris is the capital of France.")
        with Tapestry() as t:
            SemanticMemoryUpsert(
                response=response,
                llm=llm,
                store=store,
                _config=KnotConfig(id="upsert"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        count = result.outputs["upsert"]
        assert count == 2
        assert len(store.data) == 2

    async def test_deduplicates_existing_facts(self) -> None:
        store = RecordingMemoryStore()
        llm = StubLLMProvider(["existing fact"])
        response = AgentResponse(content="existing fact")
        import hashlib
        key = "fact:" + hashlib.sha256("existing fact".encode()).hexdigest()[:16]
        await store.store(key, {"fact": "existing fact"})

        with Tapestry() as t:
            SemanticMemoryUpsert(
                response=response,
                llm=llm,
                store=store,
                _config=KnotConfig(id="upsert"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        count = result.outputs["upsert"]
        assert count == 0

    async def test_returns_zero_for_empty_response(self) -> None:
        store = RecordingMemoryStore()
        llm = StubLLMProvider([""])
        response = AgentResponse(content="")
        with Tapestry() as t:
            SemanticMemoryUpsert(
                response=response,
                llm=llm,
                store=store,
                _config=KnotConfig(id="upsert"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["upsert"] == 0
