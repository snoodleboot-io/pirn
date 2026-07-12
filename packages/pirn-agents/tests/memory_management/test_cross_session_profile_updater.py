"""Unit tests for :class:`CrossSessionProfileUpdater`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.cross_session_profile_updater import (
    CrossSessionProfileUpdater,
)
from pirn_agents.memory_management.profile_key import ProfileKey
from tests.memory_management.conftest import RecordingMemoryStore


def _make_knot() -> CrossSessionProfileUpdater:
    with Tapestry():
        return CrossSessionProfileUpdater(
            key=ProfileKey(namespace="user", subject_id="u1"),
            incoming_fields={},
            store=RecordingMemoryStore(),
            now=datetime(2026, 1, 1, tzinfo=UTC),
            _config=KnotConfig(id="cspu"),
        )


class TestCrossSessionProfileUpdater(unittest.IsolatedAsyncioTestCase):
    async def test_creates_profile_when_absent(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        key = ProfileKey(namespace="user", subject_id="u1", session_id="s1")
        profile = await knot.process(
            key=key,
            incoming_fields={"name": "Ada"},
            store=store,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert profile.fields == {"name": "Ada"}
        assert profile.session_ids == ("s1",)
        assert "profile:user:u1" in store.data

    async def test_persists_across_sessions_without_clobbering(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
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
        store = RecordingMemoryStore()
        key = ProfileKey(namespace="entity", subject_id="acme")
        await knot.process(
            key=key,
            incoming_fields={"tier": "gold"},
            store=store,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert store.stored == ["profile:entity:acme"]

    async def test_repeated_session_id_not_duplicated(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
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
        with self.assertRaises(TypeError):
            await knot.process(
                key="bad",  # type: ignore[arg-type]
                incoming_fields={},
                store=RecordingMemoryStore(),
                now=datetime(2026, 1, 1, tzinfo=UTC),
            )

    async def test_rejects_non_store(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                key=ProfileKey(namespace="user", subject_id="u1"),
                incoming_fields={},
                store="bad",  # type: ignore[arg-type]
                now=datetime(2026, 1, 1, tzinfo=UTC),
            )
