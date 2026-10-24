"""Unit tests for :class:`RankedMemory` as ``Payload[RankedMemoryFrame, MemoryRecord]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.management.ranked_memory import RankedMemory
from pirn_agents.memory.management.ranked_memory_frame import RankedMemoryFrame
from tests.memory_management.conftest import make_record


def _ranked(record_id: str = "r1", score: float = 1.5) -> RankedMemory:
    return RankedMemory(
        record=make_record(id=record_id),
        score=score,
        relevance=0.5,
        recency=0.6,
        importance=0.4,
    )


class TestRankedMemoryPayload:
    def test_is_a_payload_with_frame_and_data(self) -> None:
        ranked = _ranked()

        assert isinstance(ranked, Payload)
        assert isinstance(ranked.metadata, RankedMemoryFrame)
        assert (
            ranked.metadata.score,
            ranked.metadata.relevance,
            ranked.metadata.recency,
            ranked.metadata.importance,
        ) == (1.5, 0.5, 0.6, 0.4)
        assert isinstance(ranked.data, MemoryRecord)
        assert ranked.data.data.id == "r1"

    def test_audit_dict_has_both_halves(self) -> None:
        audit = _ranked()._pirn_audit_dict()

        assert audit["score"] == 1.5
        assert audit["record"] == _ranked().data.to_payload()

    def test_equality_is_structural(self) -> None:
        assert _ranked() == _ranked()
        assert _ranked() != _ranked(score=2.0)
        assert _ranked() != _ranked(record_id="r2")
