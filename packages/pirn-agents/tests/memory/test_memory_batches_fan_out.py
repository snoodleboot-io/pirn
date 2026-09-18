"""A batch of independent memory writes is a fan-out, not an ``await`` loop.

``SemanticFactWriter``, ``MemoryEvictor`` and ``MemoryConsolidator`` each looped
over their batch awaiting one store or summariser call at a time inside a single
``process()`` (PIR-873). The engine saw one knot: one lineage row, one outcome
for the whole batch, and no concurrency whatever the run's caps said.

Each is now a ``NestedRunKnot`` fanning the batch out over one knot per item, so
these tests assert two things the old shape could not do:

* **per-item lineage** — the inner run has a row per item, with the item's own
  id and outcome;
* **real concurrency** — every item's I/O is in flight at the same time, proved
  by an ``asyncio.Barrier`` the batch can only pass if the calls overlap. Under
  the old sequential loop the first item waits on a barrier the others never
  reach, and the test times out.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.memory.management.memory_consolidator import MemoryConsolidator
from pirn_agents.memory.management.memory_eviction_policy import MemoryEvictionPolicy
from pirn_agents.memory.management.memory_evictor import MemoryEvictor
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.management.near_duplicate_grouper import NearDuplicateGrouper
from pirn_agents.memory.patterns.semantic_fact_writer import SemanticFactWriter
from pirn_agents.memory.stores.memory_store import MemoryStore
from tests.memory_management.conftest import RecordingMemoryStore, StubSummarizer, make_record


class _BarrierStore(MemoryStore):
    """A store whose writes and forgets only complete once ``parties`` overlap."""

    def __init__(self, parties: int) -> None:
        self._barrier = asyncio.Barrier(parties)
        self.stored: list[str] = []
        self.forgotten: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        await self._barrier.wait()
        self.stored.append(key)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        return ()

    async def forget(self, key: str) -> None:
        await self._barrier.wait()
        self.forgotten.append(key)

    async def close(self) -> None:
        return None


class _BarrierSummarizer(StubSummarizer):
    """A summariser that only answers once ``parties`` groups are being summarised."""

    def __init__(self, parties: int) -> None:
        super().__init__()
        self._barrier = asyncio.Barrier(parties)

    async def summarize(self, contents: Sequence[str]) -> str:
        await self._barrier.wait()
        return await super().summarize(contents)


class _EvictEverything(MemoryEvictionPolicy):
    """Selects every candidate, in the order it was handed them."""

    def select(
        self,
        records: Sequence[MemoryRecord],
        *,
        now: datetime,
        capacity: int | None = None,
    ) -> tuple[MemoryRecord, ...]:
        return tuple(records)


async def _inner_rows(tapestry: Tapestry, run: RunResult) -> dict[str, str]:
    """``{knot_id: outcome}`` over every inner run this run started."""
    children = await tapestry.history.children_of(run.run_id)
    return {row.knot_id: row.outcome for child in children for row in child.lineage}


class TestSemanticFactWriterFansOut:
    async def test_each_fact_gets_its_own_lineage_row(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(
                facts=["the sky is blue", "water is wet", "ice floats"],
                store=store,
                clock=FrozenClock(epoch=datetime(2026, 1, 1, tzinfo=UTC)),
                _config=KnotConfig(id="sfw"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=writer)

        # Assert
        assert run.succeeded, run.exceptions
        assert run.outputs["sfw"] == 3
        rows = await _inner_rows(tapestry, run)
        assert {"fact_0", "fact_1", "fact_2"} <= set(rows)
        assert {rows[f"fact_{index}"] for index in range(3)} == {"ok"}
        assert len(store.stored) == 3

    async def test_the_whole_batch_shares_one_reproducible_timestamp(self) -> None:
        # Arrange — a frozen clock is the point of injecting one at all.
        store = RecordingMemoryStore()
        frozen = datetime(2026, 1, 1, tzinfo=UTC)
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(
                facts=["a", "b"],
                store=store,
                clock=FrozenClock(epoch=frozen),
                _config=KnotConfig(id="sfw"),
            )

        # Act
        await tapestry.run(RunRequest(), terminals=writer)

        # Assert
        assert {entry["stored_at"] for entry in store.data.values()} == {frozen.isoformat()}

    async def test_the_writes_are_in_flight_together(self) -> None:
        # Arrange — three writes that can only finish if they overlap.
        store = _BarrierStore(parties=3)
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(
                facts=["a", "b", "c"], store=store, _config=KnotConfig(id="sfw")
            )

        # Act — the old sequential loop deadlocks here.
        run = await asyncio.wait_for(tapestry.run(RunRequest(), terminals=writer), timeout=10)

        # Assert
        assert run.succeeded, run.exceptions
        assert len(store.stored) == 3

    async def test_an_empty_batch_starts_no_inner_run(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry() as tapestry:
            writer = SemanticFactWriter(facts=[], store=store, _config=KnotConfig(id="sfw"))

        # Act
        run = await tapestry.run(RunRequest(), terminals=writer)

        # Assert
        assert run.outputs["sfw"] == 0
        assert await tapestry.history.children_of(run.run_id) == []

    async def test_a_non_string_fact_is_still_refused_before_any_write(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry():
            writer = SemanticFactWriter(facts=[], store=store, _config=KnotConfig(id="sfw"))

        # Act / Assert — validation stays in the outer ``process()``.
        with pytest.raises(TypeError):
            await writer.process(facts=["ok", 42], store=store)  # type: ignore[list-item]
        assert store.stored == []


class TestMemoryEvictorFansOut:
    @staticmethod
    def _records() -> list[MemoryRecord]:
        return [make_record(id=f"rec-{index}", content=f"c{index}") for index in range(3)]

    async def test_each_eviction_gets_its_own_lineage_row(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        records = self._records()
        for record in records:
            await store.store(record.data.id, record.to_payload())
        with Tapestry() as tapestry:
            evictor = MemoryEvictor(
                records=records,
                policy=_EvictEverything(),
                store=store,
                now=datetime(2026, 1, 1, tzinfo=UTC),
                _config=KnotConfig(id="evictor"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=evictor)

        # Assert
        assert run.succeeded, run.exceptions
        assert run.outputs["evictor"] == ("rec-0", "rec-1", "rec-2")
        rows = await _inner_rows(tapestry, run)
        assert {"evicted_0", "evicted_1", "evicted_2"} <= set(rows)
        assert store.forgotten == ["rec-0", "rec-1", "rec-2"] or sorted(store.forgotten) == [
            "rec-0",
            "rec-1",
            "rec-2",
        ]

    async def test_the_evictions_are_in_flight_together(self) -> None:
        # Arrange
        store = _BarrierStore(parties=3)
        with Tapestry() as tapestry:
            evictor = MemoryEvictor(
                records=self._records(),
                policy=_EvictEverything(),
                store=store,
                now=datetime(2026, 1, 1, tzinfo=UTC),
                _config=KnotConfig(id="evictor"),
            )

        # Act — the old sequential loop deadlocks here.
        run = await asyncio.wait_for(tapestry.run(RunRequest(), terminals=evictor), timeout=10)

        # Assert
        assert run.succeeded, run.exceptions
        assert len(store.forgotten) == 3

    async def test_evicting_nothing_starts_no_inner_run(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry() as tapestry:
            evictor = MemoryEvictor(
                records=[],
                policy=_EvictEverything(),
                store=store,
                now=datetime(2026, 1, 1, tzinfo=UTC),
                _config=KnotConfig(id="evictor"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=evictor)

        # Assert
        assert run.outputs["evictor"] == ()
        assert await tapestry.history.children_of(run.run_id) == []


class TestMemoryConsolidatorFansOut:
    @staticmethod
    def _two_groups() -> list[MemoryRecord]:
        """Two pairs of near-duplicates: ``alpha``-ish and ``omega``-ish."""
        return [
            make_record(id="a1", content="alpha beta gamma", kind="episodic"),
            make_record(id="a2", content="alpha beta gamma delta", kind="episodic"),
            make_record(id="z1", content="omega psi chi", kind="episodic"),
            make_record(id="z2", content="omega psi chi phi", kind="episodic"),
        ]

    async def test_each_group_and_each_write_gets_its_own_lineage_row(self) -> None:
        # Arrange
        store = RecordingMemoryStore()
        with Tapestry() as tapestry:
            consolidator = MemoryConsolidator(
                records=self._two_groups(),
                summarizer=StubSummarizer(),
                grouper=NearDuplicateGrouper(threshold=0.5),
                store=store,
                _config=KnotConfig(id="consolidator"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=consolidator)

        # Assert
        assert run.succeeded, run.exceptions
        consolidated = run.outputs["consolidator"]
        assert len(consolidated) == 2
        rows = await _inner_rows(tapestry, run)
        assert {"group_0", "group_1", "stored_0", "stored_1"} <= set(rows)
        assert len(store.stored) == 2

    async def test_the_summaries_are_in_flight_together(self) -> None:
        # Arrange
        with Tapestry() as tapestry:
            consolidator = MemoryConsolidator(
                records=self._two_groups(),
                summarizer=_BarrierSummarizer(parties=2),
                grouper=NearDuplicateGrouper(threshold=0.5),
                _config=KnotConfig(id="consolidator"),
            )

        # Act — the old sequential loop deadlocks here.
        run = await asyncio.wait_for(tapestry.run(RunRequest(), terminals=consolidator), timeout=10)

        # Assert
        assert run.succeeded, run.exceptions
        assert len(run.outputs["consolidator"]) == 2

    async def test_clean_input_starts_no_inner_run(self) -> None:
        # Arrange — one episodic record cannot form a group of two.
        with Tapestry() as tapestry:
            consolidator = MemoryConsolidator(
                records=[make_record(id="only", content="solo", kind="episodic")],
                summarizer=StubSummarizer(),
                _config=KnotConfig(id="consolidator"),
            )

        # Act
        run = await tapestry.run(RunRequest(), terminals=consolidator)

        # Assert
        assert run.outputs["consolidator"] == []
        assert await tapestry.history.children_of(run.run_id) == []
