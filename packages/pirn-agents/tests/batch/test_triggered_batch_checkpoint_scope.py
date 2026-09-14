"""Checkpoint scoping across trigger fires (PIR-803 / WS8-W3).

``TriggeredBatch`` reuses one :class:`MapAgent` for every fire, and
``MapAgent`` now resumes from a shared ``RunHistory``'s lineage instead of a
checkpoint store (ADR agents-speaks-core, WS4b): an item's knot id is
``item:<batch_id>:<key>``, and a re-run with the same ``history=`` skips any
item whose id already has an ``Ok`` lineage row. Under a single namespace
that made fire 2 skip everything fire 1 had completed, even though
``inputs_fn(ordinal)`` exists precisely to hand each fire *fresh* data.
These tests pin the fix: resume is scoped to one fire (via
``checkpoint_scope``, which becomes part of the item knot id), so
resumption still works *within* a fire while fires stay independent.
"""

from __future__ import annotations

import pytest
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.skipped import Skipped

from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.batch.triggered_batch import TriggeredBatch
from tests.batch.batch_doubles import RecordingTrigger, StubAgent


def _by_customer(item: object) -> str:
    """Key items by their own value — the customer-id shape that collides."""
    return str(item)


async def _completed(history: InMemoryHistory, batch_id: str, key: str) -> bool:
    """Whether an item's knot has an ``Ok`` lineage row under this batch/key."""
    rows = await history.query_lineage_by_knot_id(f"item:{batch_id}:{key}")
    return any(row.outcome == "ok" for row in rows)


async def test_a_later_fire_reruns_keys_an_earlier_fire_completed() -> None:
    """The defect: repeating keys across fires must not silently skip fire 2.

    ``inputs_fn`` returns the same two customer ids each fire (a fresh data
    window for the same customers). Before the fix fire 2 skipped both and
    reported ``completed_count == 0`` out of ``total == 2`` — a success that
    processed nothing.
    """
    history = InMemoryHistory()
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=history,
    )

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
    history = InMemoryHistory()
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=history,
    )
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
    """Per-fire scoping is observable in lineage, not just in the results."""
    history = InMemoryHistory()
    runner = MapAgent(
        run_item=StubAgent(),
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=history,
    )

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: [f"c{ordinal}"],
    )
    _ = [progress async for progress in triggered.run()]

    assert await _completed(history, "batch:1", "c1")
    assert await _completed(history, "batch:2", "c2")
    # Nothing is recorded under the unscoped batch id, so fires never collide.
    assert not await _completed(history, "batch", "c1")


async def test_an_interrupted_fire_resumes_where_it_left_off() -> None:
    """Crash-resumption *within* one fire survives per-fire scoping.

    The first process dies with item ``"d"`` of fire 2 unfinished (a permanent
    failure stands in for the crash — a failed item leaves no ``Ok`` lineage
    row). The replacement process replays the same trigger ordinals against
    the same history: fire 1 is entirely skipped, and fire 2 re-runs only
    ``"d"``.
    """
    history = InMemoryHistory()
    windows: dict[int, list[object]] = {1: ["a", "b"], 2: ["c", "d"]}

    first_agent = StubAgent(fail_items={"d"})
    first = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=MapAgent(
            run_item=first_agent,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ),
        inputs_fn=lambda ordinal: windows[ordinal],
    )
    crashed = [progress async for progress in first.run()]
    assert [progress.completed_count for progress in crashed] == [2, 1]

    second_agent = StubAgent()
    second = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=MapAgent(
            run_item=second_agent,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ),
        inputs_fn=lambda ordinal: windows[ordinal],
    )
    resumed = [progress async for progress in second.run()]

    assert second_agent.calls == ["d"]  # only the unfinished item re-ran
    assert [progress.total for progress in resumed] == [2, 2]
    assert [progress.completed_count for progress in resumed] == [0, 1]


async def test_map_agent_resumes_within_a_scope_and_isolates_across_scopes() -> None:
    """The scoping seam itself: same scope resumes, a different scope does not."""
    history = InMemoryHistory()

    first = StubAgent(fail_items={"b"})
    _ = [
        result
        async for result in MapAgent(
            run_item=first,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ).run(["a", "b"], checkpoint_scope="7")
    ]
    assert first.calls == ["a", "b"]

    # Same scope: "a" is durable, so only "b" re-runs.
    same = StubAgent()
    resumed = [
        result
        async for result in MapAgent(
            run_item=same,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ).run(["a", "b"], checkpoint_scope="7")
    ]
    assert same.calls == ["b"]
    by_key = {r.key: r for r in resumed}
    assert isinstance(by_key["a"].outcome, Skipped)
    assert by_key["b"].succeeded

    # A different scope shares nothing.
    other = StubAgent()
    _ = [
        result
        async for result in MapAgent(
            run_item=other,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ).run(["a", "b"], checkpoint_scope="8")
    ]
    assert other.calls == ["a", "b"]


async def test_shared_checkpoint_opts_back_into_cross_fire_dedup() -> None:
    """The escape hatch: one namespace for every fire, explicitly requested."""
    history = InMemoryHistory()
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=history,
    )

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
    history = InMemoryHistory()
    seen: list[int] = []

    def inputs_fn(ordinal: int) -> list[object]:
        seen.append(ordinal)
        return [f"c{ordinal}"]

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2, first_ordinal=41),
        map_agent=MapAgent(
            run_item=StubAgent(),
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        ),
        inputs_fn=inputs_fn,
    )
    progresses = [progress async for progress in triggered.run()]

    assert seen == [41, 42]
    assert [progress.batch_id for progress in progresses] == ["batch-41", "batch-42"]
    assert await _completed(history, "batch:41", "c41")


async def test_a_trigger_without_a_usable_ordinal_falls_back_to_the_local_counter() -> None:
    """``fire_ordinal`` is a convention, not a ``Trigger`` guarantee."""
    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2, first_ordinal=None),
        map_agent=MapAgent(run_item=StubAgent(), _config=KnotConfig(id="map-agent"), concurrency=1),
        inputs_fn=lambda ordinal: ["a"],
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress.batch_id for progress in progresses] == ["batch-1", "batch-2"]


def test_rejects_a_non_bool_shared_checkpoint() -> None:
    with pytest.raises(TypeError):
        TriggeredBatch(
            trigger=RecordingTrigger(fires=1),
            map_agent=MapAgent(
                run_item=StubAgent(), _config=KnotConfig(id="map-agent"), concurrency=1
            ),
            inputs_fn=lambda ordinal: ["a"],
            shared_checkpoint="yes",  # type: ignore[arg-type]
        )


async def test_rejects_a_non_str_checkpoint_scope() -> None:
    runner = MapAgent(run_item=StubAgent(), _config=KnotConfig(id="map-agent"), concurrency=1)
    with pytest.raises(TypeError):
        _ = [result async for result in runner.run(["a"], checkpoint_scope=7)]  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# PIR-813: the ordinal is not a resume key across process lifetimes
# --------------------------------------------------------------------------


async def test_a_replacement_process_silently_drops_repeat_keys_without_scope_fn() -> None:
    """The defect, demonstrated end to end.

    The ordinal lives in the trigger's generator, so a replacement process
    restarts numbering at 1 and its fire 1 adopts the *previous* process's fire-1
    skip-set. A customer seen in both runs is dropped — reported as completed
    having never been processed.
    """
    history = InMemoryHistory()
    proc1_agent, proc2_agent = StubAgent(), StubAgent()
    proc1_windows: dict[int, list[object]] = {1: ["a", "b"], 2: ["c", "a"]}
    proc2_windows: dict[int, list[object]] = {1: ["a", "d"], 2: ["e", "a"]}

    for agent, windows in ((proc1_agent, proc1_windows), (proc2_agent, proc2_windows)):
        # A fresh TriggeredBatch each time == a fresh process, but the SAME
        # durable history, which is the whole point of a checkpoint.
        runner = MapAgent(
            run_item=agent,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        )
        triggered = TriggeredBatch(
            trigger=RecordingTrigger(fires=2),
            map_agent=runner,
            inputs_fn=lambda ordinal, w=windows: w[ordinal],
        )
        [progress async for progress in triggered.run()]

    # Dispatch order among same-depth sibling items is the engine's own
    # (topological, tie-broken by knot id), not input order, so compare as
    # multisets: what matters is that every item ran, none was dropped.
    assert sorted(proc1_agent.calls) == sorted(["a", "b", "c", "a"])
    # 'a' appears in both of proc2's windows and is dropped from both, because
    # scopes "1" and "2" already hold it from proc1.
    assert sorted(proc2_agent.calls) == sorted(["d", "e"])


async def test_scope_fn_keeps_a_replacement_process_processing_its_own_window() -> None:
    """The fix: a window identity derived from the data does not restart at 1."""
    history = InMemoryHistory()
    proc1_agent, proc2_agent = StubAgent(), StubAgent()
    proc1_windows: dict[int, list[object]] = {1: ["a", "b"], 2: ["c", "a"]}
    proc2_windows: dict[int, list[object]] = {1: ["a", "d"], 2: ["e", "a"]}
    # What a real caller supplies: the window it is producing, not a counter.
    proc1_scopes = {1: "2026-08-15T00:00", 2: "2026-08-15T12:00"}
    proc2_scopes = {1: "2026-08-16T00:00", 2: "2026-08-16T12:00"}

    for agent, windows, scopes in (
        (proc1_agent, proc1_windows, proc1_scopes),
        (proc2_agent, proc2_windows, proc2_scopes),
    ):
        runner = MapAgent(
            run_item=agent,
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
            history=history,
        )
        triggered = TriggeredBatch(
            trigger=RecordingTrigger(fires=2),
            map_agent=runner,
            inputs_fn=lambda ordinal, w=windows: w[ordinal],
            scope_fn=lambda ordinal, s=scopes: s[ordinal],
        )
        [progress async for progress in triggered.run()]

    # See the sibling-order note above: compare as multisets.
    assert sorted(proc1_agent.calls) == sorted(["a", "b", "c", "a"])
    # Nothing dropped: proc2's windows are its own.
    assert sorted(proc2_agent.calls) == sorted(["a", "d", "e", "a"])


async def test_a_repeated_scope_is_refused_rather_than_silently_shared() -> None:
    """Two fires in one namespace make the second report success doing nothing."""
    runner = MapAgent(
        run_item=StubAgent(),
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=InMemoryHistory(),
    )
    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: ["c1"],
        scope_fn=lambda ordinal: "always-the-same",
    )

    with pytest.raises(ValueError, match="already used"):
        [progress async for progress in triggered.run()]


async def test_scope_fn_must_return_a_non_empty_str() -> None:
    def _runner() -> MapAgent:
        return MapAgent(
            run_item=StubAgent(),
            _config=KnotConfig(id="map-agent"),
            concurrency=1,
            key_fn=_by_customer,
        )

    for bad, exc in ((lambda ordinal: 7, TypeError), (lambda ordinal: "", ValueError)):
        triggered = TriggeredBatch(
            trigger=RecordingTrigger(fires=1),
            map_agent=_runner(),
            inputs_fn=lambda ordinal: ["c1"],
            scope_fn=bad,
        )
        with pytest.raises(exc):
            [progress async for progress in triggered.run()]


def test_scope_fn_must_be_callable() -> None:
    with pytest.raises(TypeError, match="scope_fn"):
        TriggeredBatch(
            trigger=RecordingTrigger(fires=1),
            map_agent=MapAgent(
                run_item=StubAgent(),
                _config=KnotConfig(id="map-agent"),
                concurrency=1,
                key_fn=_by_customer,
            ),
            inputs_fn=lambda ordinal: [],
            scope_fn="not-callable",  # type: ignore[arg-type]
        )


async def test_without_scope_fn_the_ordinal_still_scopes_each_fire() -> None:
    """The default path is unchanged — PIR-803's guarantee still holds."""
    agent = StubAgent()
    runner = MapAgent(
        run_item=agent,
        _config=KnotConfig(id="map-agent"),
        concurrency=1,
        key_fn=_by_customer,
        history=InMemoryHistory(),
    )
    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=runner,
        inputs_fn=lambda ordinal: ["c1", "c2"],
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress.completed_count for progress in progresses] == [2, 2]
    assert agent.calls == ["c1", "c2", "c1", "c2"]
