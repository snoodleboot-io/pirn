"""Checkpoint scoping across trigger fires (PIR-803 / WS8-W3).

``TriggeredBatch`` reuses one :class:`MapAgent` for every fire, and ``MapAgent``
re-seeds its skip-set from the checkpointer on every ``run()``. Under a single
checkpoint namespace that made fire 2 skip everything fire 1 had completed, even
though ``inputs_fn(ordinal)`` exists precisely to hand each fire *fresh* data.
These tests pin the fix: a checkpoint is scoped to one fire, so resumption still
works *within* a fire while fires stay independent.
"""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_checkpointer import BatchCheckpointer
from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.batch.triggered_batch import TriggeredBatch
from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from tests.batch.batch_doubles import RecordingTrigger, StubAgent


def _by_customer(item: object) -> str:
    """Key items by their own value — the customer-id shape that collides."""
    return str(item)


async def test_a_later_fire_reruns_keys_an_earlier_fire_completed() -> None:
    """The defect: repeating keys across fires must not silently skip fire 2.

    ``inputs_fn`` returns the same two customer ids each fire (a fresh data
    window for the same customers). Before the fix fire 2 skipped both and
    reported ``completed_count == 0`` out of ``total == 2`` — a success that
    processed nothing.
    """
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    agent = StubAgent()
    runner = MapAgent(agent, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer)

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: ["c1", "c2"],
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress.total for progress in progresses] == [2, 2]
    assert [progress.completed_count for progress in progresses] == [2, 2]
    assert agent.calls == ["c1", "c2", "c1", "c2"]


async def test_partially_overlapping_fires_rerun_the_colliding_subset() -> None:
    """Only the colliding keys were dropped, which is what hid the bug so long."""
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    agent = StubAgent()
    runner = MapAgent(agent, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer)
    windows: dict[int, list[object]] = {1: ["c1", "c2"], 2: ["c2", "c3"]}

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: windows[ordinal],
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress.completed_count for progress in progresses] == [2, 2]
    assert agent.calls == ["c1", "c2", "c2", "c3"]


async def test_each_fire_checkpoints_under_its_own_key() -> None:
    """Per-fire scoping is observable in the store, not just in the results."""
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="daily")
    runner = MapAgent(StubAgent(), concurrency=1, key_fn=_by_customer, checkpointer=checkpointer)

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: [f"c{ordinal}"],
    )
    _ = [progress async for progress in triggered.run()]

    assert (await checkpointer.scoped("1").load()).completed_keys == frozenset({"c1"})
    assert (await checkpointer.scoped("2").load()).completed_keys == frozenset({"c2"})
    # Nothing is written under the unscoped id, so fires never collide.
    assert await store.load("daily") is None


async def test_an_interrupted_fire_resumes_where_it_left_off() -> None:
    """Crash-resumption *within* one fire survives per-fire scoping.

    The first process dies with item ``"d"`` of fire 2 unfinished (a permanent
    failure stands in for the crash — a failed item is never checkpointed). The
    replacement process replays the same trigger ordinals against the same
    store: fire 1 is entirely skipped, and fire 2 re-runs only ``"d"``.
    """
    store = InMemorySessionStore()
    windows: dict[int, list[object]] = {1: ["a", "b"], 2: ["c", "d"]}

    first_agent = StubAgent(fail_items={"d"})
    first = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=MapAgent(
            first_agent,
            concurrency=1,
            key_fn=_by_customer,
            checkpointer=BatchCheckpointer(store=store, batch_id="daily"),
        ),
        inputs_fn=lambda ordinal: windows[ordinal],
    )
    crashed = [progress async for progress in first.run()]
    assert [progress.completed_count for progress in crashed] == [2, 1]

    second_agent = StubAgent()
    second = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=MapAgent(
            second_agent,
            concurrency=1,
            key_fn=_by_customer,
            checkpointer=BatchCheckpointer(store=store, batch_id="daily"),
        ),
        inputs_fn=lambda ordinal: windows[ordinal],
    )
    resumed = [progress async for progress in second.run()]

    assert second_agent.calls == ["d"]  # only the unfinished item re-ran
    assert [progress.total for progress in resumed] == [2, 2]
    assert [progress.completed_count for progress in resumed] == [0, 1]


async def test_map_agent_resumes_within_a_scope_and_isolates_across_scopes() -> None:
    """The scoping seam itself: same scope resumes, a different scope does not."""
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="daily")

    first = StubAgent(fail_items={"b"})
    _ = [
        result
        async for result in MapAgent(
            first, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer
        ).run(["a", "b"], checkpoint_scope="7")
    ]
    assert first.calls == ["a", "b"]

    # Same scope: "a" is durable, so only "b" re-runs.
    same = StubAgent()
    resumed = [
        result
        async for result in MapAgent(
            same, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer
        ).run(["a", "b"], checkpoint_scope="7")
    ]
    assert same.calls == ["b"]
    assert {r.key: r.status for r in resumed} == {
        "a": BatchItemStatus.SKIPPED,
        "b": BatchItemStatus.OK,
    }

    # A different scope shares nothing.
    other = StubAgent()
    _ = [
        result
        async for result in MapAgent(
            other, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer
        ).run(["a", "b"], checkpoint_scope="8")
    ]
    assert other.calls == ["a", "b"]


async def test_shared_checkpoint_opts_back_into_cross_fire_dedup() -> None:
    """The escape hatch: one namespace for every fire, explicitly requested."""
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    agent = StubAgent()
    runner = MapAgent(agent, concurrency=1, key_fn=_by_customer, checkpointer=checkpointer)

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: ["c1", "c2"],
        shared_checkpoint=True,
    )
    progresses = [progress async for progress in triggered.run()]

    assert agent.calls == ["c1", "c2"]  # fire 2 de-dups against fire 1
    assert [progress.completed_count for progress in progresses] == [2, 0]


async def test_batch_id_and_checkpoint_scope_follow_the_triggers_fire_ordinal() -> None:
    """A trigger whose ordinals do not start at 1 still drives consistent ids."""
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="daily")
    seen: list[int] = []

    def inputs_fn(ordinal: int) -> list[object]:
        seen.append(ordinal)
        return [f"c{ordinal}"]

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2, first_ordinal=41),
        map_agent=MapAgent(
            StubAgent(), concurrency=1, key_fn=_by_customer, checkpointer=checkpointer
        ),
        inputs_fn=inputs_fn,
    )
    progresses = [progress async for progress in triggered.run()]

    assert seen == [41, 42]
    assert [progress.batch_id for progress in progresses] == ["batch-41", "batch-42"]
    assert (await checkpointer.scoped("41").load()).completed_keys == frozenset({"c41"})


async def test_a_trigger_without_a_usable_ordinal_falls_back_to_the_local_counter() -> None:
    """``fire_ordinal`` is a convention, not a ``Trigger`` guarantee."""
    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2, first_ordinal=None),
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=lambda ordinal: ["a"],
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress.batch_id for progress in progresses] == ["batch-1", "batch-2"]


def test_scoped_rejects_an_empty_suffix() -> None:
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    with pytest.raises(ValueError):
        checkpointer.scoped("")


def test_rejects_a_non_bool_shared_checkpoint() -> None:
    with pytest.raises(TypeError):
        TriggeredBatch(
            trigger=RecordingTrigger(fires=1),
            map_agent=MapAgent(StubAgent(), concurrency=1),
            inputs_fn=lambda ordinal: ["a"],
            shared_checkpoint="yes",  # type: ignore[arg-type]
        )


async def test_rejects_a_non_str_checkpoint_scope() -> None:
    runner = MapAgent(StubAgent(), concurrency=1)
    with pytest.raises(TypeError):
        _ = [result async for result in runner.run(["a"], checkpoint_scope=7)]  # type: ignore[arg-type]
