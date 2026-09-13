"""Unit tests for :class:`CrossSessionProfileUpdater`.

ADR "agents speaks core" WS3 part 4: ``store`` is now a real
:class:`~pirn_agents.memory.stores.keyed_lineage_store.KeyedLineageStore`
(backed by real ``InMemoryHistory``/``InMemoryDataStore``), not a
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` double.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory.management.cross_session_profile_updater import (
    CrossSessionProfileUpdater,
)
from pirn_agents.memory.management.profile_key import ProfileKey
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore


def _make_store() -> KeyedLineageStore:
    return KeyedLineageStore(history=InMemoryHistory(), data_store=InMemoryDataStore())


def _make_knot() -> CrossSessionProfileUpdater:
    with Tapestry():
        return CrossSessionProfileUpdater(
            key=ProfileKey(namespace="user", subject_id="u1"),
            incoming_fields={},
            store=_make_store(),
            now=datetime(2026, 1, 1, tzinfo=UTC),
            _config=KnotConfig(id="cspu"),
        )


class TestCrossSessionProfileUpdater(unittest.IsolatedAsyncioTestCase):
    async def test_creates_profile_when_absent(self) -> None:
        knot = _make_knot()
        store = _make_store()
        key = ProfileKey(namespace="user", subject_id="u1", session_id="s1")
        profile = await knot.process(
            key=key,
            incoming_fields={"name": "Ada"},
            store=store,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert profile.fields == {"name": "Ada"}
        assert profile.session_ids == ("s1",)
        assert await store.get(namespace="profile", key="profile:user:u1") is not None

    async def test_persists_across_sessions_without_clobbering(self) -> None:
        knot = _make_knot()
        store = _make_store()
        key_s1 = ProfileKey(namespace="user", subject_id="u1", session_id="s1")
        await knot.process(
            key=key_s1,
            incoming_fields={"name": "Ada", "prefs": {"theme": "dark"}},
            store=store,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # A later session updates only one nested key.
        key_s2 = ProfileKey(namespace="user", subject_id="u1", session_id="s2")
        profile = await knot.process(
            key=key_s2,
            incoming_fields={"prefs": {"lang": "en"}},
            store=store,
            now=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert profile.fields == {"name": "Ada", "prefs": {"theme": "dark", "lang": "en"}}
        assert profile.session_ids == ("s1", "s2")

    async def test_provider_neutral_lookup_uses_storage_key(self) -> None:
        knot = _make_knot()
        store = _make_store()
        key = ProfileKey(namespace="entity", subject_id="acme")
        await knot.process(
            key=key,
            incoming_fields={"tier": "gold"},
            store=store,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        rows = await store.history.query_lineage_by_knot_id(
            KeyedLineageStore.identity("profile", "profile:entity:acme")
        )
        assert len(rows) == 1

    async def test_repeated_session_id_not_duplicated(self) -> None:
        knot = _make_knot()
        store = _make_store()
        key = ProfileKey(namespace="user", subject_id="u1", session_id="s1")
        await knot.process(
            key=key, incoming_fields={"a": 1}, store=store, now=datetime(2026, 1, 1, tzinfo=UTC)
        )
        profile = await knot.process(
            key=key, incoming_fields={"b": 2}, store=store, now=datetime(2026, 1, 2, tzinfo=UTC)
        )
        assert profile.session_ids == ("s1",)

    async def test_rejects_non_key(self) -> None:
        knot = _make_knot()
        result = await knot(
            {
                "key": "bad",
                "incoming_fields": {},
                "store": _make_store(),
                "now": datetime(2026, 1, 1, tzinfo=UTC),
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_store(self) -> None:
        knot = _make_knot()
        result = await knot(
            {
                "key": ProfileKey(namespace="user", subject_id="u1"),
                "incoming_fields": {},
                "store": "bad",
                "now": datetime(2026, 1, 1, tzinfo=UTC),
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
