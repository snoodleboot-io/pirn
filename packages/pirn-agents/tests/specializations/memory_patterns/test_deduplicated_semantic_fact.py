"""Unit tests for :class:`DeduplicatedSemanticFact`.

The per-fact knot behind :class:`SemanticMemoryUpsert`'s fan-out (PIR-874). It
owns both halves of one fact's upsert — the dedup read and the conditional
write — so that each is a lineage row of its own.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.content_hasher import ContentHasher
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.patterns.deduplicated_semantic_fact import DeduplicatedSemanticFact
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore

_NAMESPACE = "semantic-memory"
_STORED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_store() -> KeyedLineageStore:
    return KeyedLineageStore(history=InMemoryHistory(), data_store=InMemoryDataStore())


def _make_knot(store: KeyedLineageStore, fact: str) -> DeduplicatedSemanticFact:
    with Tapestry():
        return DeduplicatedSemanticFact(
            fact=fact,
            namespace=_NAMESPACE,
            store=store,
            stored_at=_STORED_AT,
            _config=KnotConfig(id="fact_0"),
        )


class TestDeduplicatedSemanticFact(unittest.IsolatedAsyncioTestCase):
    async def test_writes_a_fact_that_is_not_on_record(self) -> None:
        store = _make_store()
        knot = _make_knot(store, "the kettle is on")
        written = await knot.process(
            fact="the kettle is on",
            namespace=_NAMESPACE,
            store=store,
            stored_at=_STORED_AT,
        )
        assert written is True
        key = ContentHasher.hash("the kettle is on")
        stored = await store.get(namespace=_NAMESPACE, key=key)
        assert stored is not None
        assert stored["content"] == "the kettle is on"
        assert stored["kind"] == "semantic"
        assert stored["provenance"]["source"] == "semantic_memory_upsert"

    async def test_reports_false_without_writing_when_already_on_record(self) -> None:
        store = _make_store()
        key = ContentHasher.hash("already known")
        await store.put(namespace=_NAMESPACE, key=key, value={"content": "already known"})
        knot = _make_knot(store, "already known")
        written = await knot.process(
            fact="already known",
            namespace=_NAMESPACE,
            store=store,
            stored_at=_STORED_AT,
        )
        assert written is False
        rows = await store.history.query_lineage_by_knot_id(
            KeyedLineageStore.identity(_NAMESPACE, key)
        )
        assert len(rows) == 1

    async def test_stamps_the_timestamp_it_was_handed(self) -> None:
        """``stored_at`` comes from the caller so one extraction's facts agree."""
        store = _make_store()
        knot = _make_knot(store, "dated fact")
        await knot.process(
            fact="dated fact",
            namespace=_NAMESPACE,
            store=store,
            stored_at=_STORED_AT,
        )
        stored = await store.get(namespace=_NAMESPACE, key=ContentHasher.hash("dated fact"))
        assert stored is not None
        assert stored["created_at"].startswith("2026-01-01")

    async def test_a_deleted_fact_is_absent_again(self) -> None:
        """PIR-873: the dedup read is ``get``, the one read a tombstone hides from."""
        store = _make_store()
        key = ContentHasher.hash("forgotten")
        knot = _make_knot(store, "forgotten")
        await knot.process(
            fact="forgotten", namespace=_NAMESPACE, store=store, stored_at=_STORED_AT
        )
        await store.delete(namespace=_NAMESPACE, key=key)
        written = await knot.process(
            fact="forgotten", namespace=_NAMESPACE, store=store, stored_at=_STORED_AT
        )
        assert written is True
