"""Unit tests for :class:`MemoryRecord`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.memory_management.memory_record import MemoryRecord
from tests.memory_management.conftest import make_provenance, make_record


class TestMemoryRecordValidation(unittest.TestCase):
    def test_rejects_empty_id(self) -> None:
        with self.assertRaises(TypeError):
            make_record(id="")

    def test_rejects_invalid_kind(self) -> None:
        with self.assertRaises(ValueError):
            MemoryRecord(
                id="r1",
                kind="working",  # type: ignore[arg-type]
                content="c",
                provenance=make_provenance(),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_rejects_out_of_range_importance(self) -> None:
        with self.assertRaises(ValueError):
            make_record(id="r1", importance=2.0)

    def test_rejects_non_provenance(self) -> None:
        with self.assertRaises(TypeError):
            MemoryRecord(
                id="r1",
                kind="episodic",
                content="c",
                provenance="bad",  # type: ignore[arg-type]
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )


class TestMemoryRecordRecencyAnchor(unittest.TestCase):
    def test_uses_last_accessed_when_present(self) -> None:
        created = datetime(2026, 1, 1, tzinfo=UTC)
        accessed = datetime(2026, 2, 1, tzinfo=UTC)
        record = make_record(id="r1", created_at=created, last_accessed=accessed)
        assert record.recency_anchor() == accessed

    def test_falls_back_to_created_at(self) -> None:
        created = datetime(2026, 1, 1, tzinfo=UTC)
        record = make_record(id="r1", created_at=created)
        assert record.recency_anchor() == created


class TestMemoryRecordRoundTrip(unittest.TestCase):
    def test_payload_round_trips(self) -> None:
        record = make_record(
            id="r1",
            kind="semantic",
            content="water is wet",
            importance=0.5,
            last_accessed=datetime(2026, 3, 1, tzinfo=UTC),
            metadata={"session_id": "s1"},
        )
        restored = MemoryRecord.from_payload(record.to_payload())
        assert restored == record

    def test_from_payload_rejects_bad_kind(self) -> None:
        record = make_record(id="r1")
        payload = dict(record.to_payload())
        payload["kind"] = "working"
        with self.assertRaises(ValueError):
            MemoryRecord.from_payload(payload)

    def test_from_payload_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            MemoryRecord.from_payload(123)
