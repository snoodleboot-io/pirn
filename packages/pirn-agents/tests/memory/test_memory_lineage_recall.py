"""Unit tests for :class:`MemoryLineageRecall`.

A writer knot needs no keyed store at all: it returns a
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord` and the
engine content-addresses it into the tapestry's ``DataStore``, recording a
``KnotLineage`` row keyed by the writer's knot id. These tests exercise that
whole path end to end — two real ``Tapestry.run()`` calls sharing one
``RunHistory``/``DataStore`` pair — rather than mocking the engine's own
lineage recording.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.memory_lineage_recall import MemoryLineageRecall


def _record(id: str, *, session_id: str = "s1") -> MemoryRecord:
    return MemoryRecord(
        id=id,
        kind="episodic",
        content=f"content-{id}",
        provenance=MemoryProvenance(source="writer", timestamp=datetime(2026, 1, 1, tzinfo=UTC)),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        metadata={"session_id": session_id},
    )


class _RecordSource(Source):
    """Test writer knot: returns a canned ``MemoryRecord``, no store write at all."""

    def __init__(self, *, record: MemoryRecord, _config: KnotConfig) -> None:
        super().__init__(_config=_config)
        self._mutable_record = record

    async def process(self, **_: object) -> MemoryRecord:
        return self._mutable_record


async def _write(
    history: InMemoryHistory, data_store: InMemoryDataStore, record: MemoryRecord
) -> None:
    with Tapestry(history=history, data_store=data_store) as t:
        _RecordSource(record=record, _config=KnotConfig(id="writer"))
        result = await t.run(RunRequest())
    assert result.succeeded


class TestMemoryLineageRecall:
    async def test_recalls_every_record_a_writer_produced(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        await _write(history, data_store, _record("e1"))
        await _write(history, data_store, _record("e2"))

        with Tapestry(history=history, data_store=data_store) as t:
            MemoryLineageRecall(
                history=history,
                data_store=data_store,
                writer_knot_id="writer",
                _config=KnotConfig(id="recall"),
            )
            result = await t.run(RunRequest())
        assert result.succeeded
        recalled = result.outputs["recall"]
        assert [r.data.id for r in recalled] == ["e1", "e2"]

    async def test_unknown_writer_id_recalls_nothing(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        await _write(history, data_store, _record("e1"))

        with Tapestry(history=history, data_store=data_store) as t:
            MemoryLineageRecall(
                history=history,
                data_store=data_store,
                writer_knot_id="no-such-writer",
                _config=KnotConfig(id="recall"),
            )
            result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["recall"] == []

    async def test_tag_filter_narrows_to_matching_records(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        await _write(history, data_store, _record("e1", session_id="s1"))
        await _write(history, data_store, _record("e2", session_id="s2"))

        with Tapestry(history=history, data_store=data_store) as t:
            MemoryLineageRecall(
                history=history,
                data_store=data_store,
                writer_knot_id="writer",
                tag_filter={"session_id": "s2"},
                _config=KnotConfig(id="recall"),
            )
            result = await t.run(RunRequest())
        assert result.succeeded
        recalled = result.outputs["recall"]
        assert [r.data.id for r in recalled] == ["e2"]

    async def test_rejects_non_run_history(self) -> None:
        data_store = InMemoryDataStore()
        with Tapestry(data_store=data_store) as t:
            MemoryLineageRecall(
                history="nope",  # type: ignore[arg-type]
                data_store=data_store,
                writer_knot_id="writer",
                _config=KnotConfig(id="recall"),
            )
            result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_empty_writer_knot_id(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        with Tapestry(history=history, data_store=data_store) as t:
            MemoryLineageRecall(
                history=history,
                data_store=data_store,
                writer_knot_id="",
                _config=KnotConfig(id="recall"),
            )
            result = await t.run(RunRequest())
        assert not result.succeeded

    def test_matches_is_a_subset_check(self) -> None:
        record = _record("e1", session_id="s1")
        assert MemoryLineageRecall._matches(record, {"session_id": "s1"})
        assert not MemoryLineageRecall._matches(record, {"session_id": "other"})
        assert not MemoryLineageRecall._matches(record, {"missing_key": "x"})
        assert MemoryLineageRecall._matches(record, {})
