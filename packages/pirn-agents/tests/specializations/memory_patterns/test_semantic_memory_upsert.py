"""Tests for :class:`SemanticMemoryUpsert`.

ADR "agents speaks core" WS3 part 4: ``store`` is now a real
:class:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`
(backed by real ``InMemoryHistory``/``InMemoryDataStore``), not a
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` double — dedup
reads ``latest_output_hash`` directly, a surface ``MemoryStore`` does not
expose.
"""

from __future__ import annotations

import unittest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.content_hasher import ContentHasher
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.patterns.semantic_memory_upsert import (
    SemanticMemoryUpsert,
)
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _make_store() -> KeyedLineageStore:
    return KeyedLineageStore(history=InMemoryHistory(), data_store=InMemoryDataStore())


def _make_knot() -> SemanticMemoryUpsert:
    with Tapestry():
        return SemanticMemoryUpsert(
            response=AgentResponse(content="x"),
            llm=StubLLMProvider(["fact1"]),
            store=_make_store(),
            _config=KnotConfig(id="upsert"),
        )


class TestSemanticMemoryUpsertProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_and_stores_facts(self) -> None:
        k = _make_knot()
        store = _make_store()
        llm = StubLLMProvider(["- Paris is the capital of France\n- The Eiffel Tower is in Paris"])
        response = AgentResponse(content="Paris is the capital of France.")
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 2

    async def test_stores_a_typed_memory_record_payload(self) -> None:
        # ADR agents-speaks-core WS3 part 3: the stored value is now a
        # MemoryRecord.to_payload(), not a bare {"fact": ...} dict.
        k = _make_knot()
        store = _make_store()
        llm = StubLLMProvider(["a new fact"])
        response = AgentResponse(content="a new fact")
        await k.process(response=response, llm=llm, store=store)
        key = ContentHasher.hash("a new fact")
        stored = await store.get(namespace="semantic-memory", key=key)
        assert stored is not None
        assert stored["content"] == "a new fact"
        assert stored["kind"] == "semantic"
        assert stored["provenance"]["source"] == "semantic_memory_upsert"

    async def test_deduplicates_against_a_freshly_written_typed_record(self) -> None:
        k = _make_knot()
        store = _make_store()
        llm = StubLLMProvider(["repeat me", "repeat me"])
        response = AgentResponse(content="repeat me")
        first = await k.process(response=response, llm=llm, store=store)
        second = await k.process(response=response, llm=llm, store=store)
        assert first == 1
        assert second == 0
        rows = await store.history.query_lineage_by_knot_id(
            KeyedLineageStore.identity("semantic-memory", ContentHasher.hash("repeat me"))
        )
        assert len(rows) == 1

    async def test_deduplicates_existing_facts(self) -> None:
        k = _make_knot()
        store = _make_store()
        llm = StubLLMProvider(["existing fact"])
        response = AgentResponse(content="existing fact")
        key = ContentHasher.hash("existing fact")
        await store.put(namespace="semantic-memory", key=key, value={"fact": "existing fact"})
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 0

    async def test_returns_zero_for_empty_response(self) -> None:
        k = _make_knot()
        store = _make_store()
        llm = StubLLMProvider([""])
        response = AgentResponse(content="")
        count = await k.process(response=response, llm=llm, store=store)
        assert count == 0

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        store = _make_store()
        result = await k({"response": AgentResponse(content="x"), "llm": "bad", "store": store})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_keyed_lineage_store(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["fact1"])
        result = await k({"response": AgentResponse(content="x"), "llm": llm, "store": "bad"})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
