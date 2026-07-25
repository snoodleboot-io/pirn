"""Unit tests for :class:`TypedMemoryWriter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_management.typed_memory_writer import TypedMemoryWriter
from tests.memory_management.conftest import RecordingMemoryStore, make_record


def _make_knot() -> TypedMemoryWriter:
    with Tapestry():
        return TypedMemoryWriter(
            record=make_record(id="r1"),
            store=RecordingMemoryStore(),
            _config=KnotConfig(id="tmw"),
        )


class TestTypedMemoryWriter(unittest.IsolatedAsyncioTestCase):
    async def test_writes_payload_under_record_id(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        record = make_record(id="mem-1", kind="semantic", content="fact")
        key = await knot.process(record=record, store=store)
        assert key == "mem-1"
        assert store.data["mem-1"]["content"] == "fact"

    async def test_written_payload_round_trips_through_store(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        record = make_record(id="mem-1", importance=0.4)
        await knot.process(record=record, store=store)
        restored = MemoryRecord.from_payload(await store.retrieve("mem-1"))
        assert restored == record

    async def test_rejects_non_record(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(record="bad", store=RecordingMemoryStore())  # type: ignore[arg-type]

    async def test_rejects_non_store(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(record=make_record(id="r1"), store="bad")  # type: ignore[arg-type]
