"""Unit tests for :class:`MemoryEvictor`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.memory_evictor import MemoryEvictor
from pirn_agents.memory_management.ttl_eviction_policy import TtlEvictionPolicy
from tests.memory_management.conftest import RecordingMemoryStore, make_record


def _make_knot() -> MemoryEvictor:
    with Tapestry():
        return MemoryEvictor(
            records=[],
            policy=TtlEvictionPolicy(ttl_seconds=3600),
            store=RecordingMemoryStore(),
            now=datetime(2026, 1, 1, tzinfo=UTC),
            _config=KnotConfig(id="me"),
        )


class TestMemoryEvictor(unittest.IsolatedAsyncioTestCase):
    async def test_forgets_selected_records_and_returns_ids(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        now = datetime(2026, 6, 1, tzinfo=UTC)
        old = make_record(id="old", created_at=now - timedelta(seconds=7200))
        fresh = make_record(id="fresh", created_at=now)
        await store.store("old", old.to_payload())
        await store.store("fresh", fresh.to_payload())
        evicted = await knot.process(
            records=[old, fresh], policy=TtlEvictionPolicy(ttl_seconds=3600), store=store, now=now
        )
        assert evicted == ("old",)
        assert store.forgotten == ["old"]
        assert "old" not in store.data and "fresh" in store.data

    async def test_no_evictions_leaves_store_untouched(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        now = datetime(2026, 6, 1, tzinfo=UTC)
        fresh = make_record(id="fresh", created_at=now)
        evicted = await knot.process(
            records=[fresh], policy=TtlEvictionPolicy(ttl_seconds=3600), store=store, now=now
        )
        assert evicted == ()
        assert store.forgotten == []

    async def test_rejects_non_policy(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                records=[],
                policy="bad",  # type: ignore[arg-type]
                store=RecordingMemoryStore(),
                now=datetime(2026, 1, 1, tzinfo=UTC),
            )

    async def test_rejects_non_store(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                records=[],
                policy=TtlEvictionPolicy(ttl_seconds=1),
                store="bad",  # type: ignore[arg-type]
                now=datetime(2026, 1, 1, tzinfo=UTC),
            )
