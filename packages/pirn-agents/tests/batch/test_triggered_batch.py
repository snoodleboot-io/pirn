"""Binding tests for :class:`TriggeredBatch` (F28-S5 / PIR-584, PIR-723 / WS8-D3).

One batch runs per trigger fire; each run yields a :class:`BatchProgress` whose
``completed_count``/``total`` is the partial-failure report, and ``inputs_fn``
receives the fire ordinal so each run can pull fresh data. Stub doubles keep it
deterministic.

The driver semantics borrowed from :func:`pirn.triggers.base.run_forever` — the
trigger is always closed on exit, and ``on_result``/``on_error`` observe each
run — are asserted here too, including the one place this deliberately departs
from ``run_forever``: a ``CancelledError`` is re-raised rather than handed to
``on_error``, so cancellation is never swallowed by an observer.
"""

from __future__ import annotations

import asyncio

import pytest
from pirn.core.run_request import RunRequest

from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.batch.event_trigger import EventTrigger
from pirn_agents.batch.interval_trigger import IntervalTrigger
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.batch.triggered_batch import TriggeredBatch
from tests.batch.batch_doubles import RecordingTrigger, StubAgent


async def _fake_sleep(delay: float) -> None:
    return None


async def test_runs_one_batch_per_fire_with_failure_report() -> None:
    trigger = IntervalTrigger(interval=0.0, max_fires=2, sleep=_fake_sleep)
    runner = MapAgent(StubAgent(fail_items={"bad"}), concurrency=4)

    triggered = TriggeredBatch(
        trigger=trigger, map_agent=runner, inputs_fn=lambda ordinal: ["ok1", "bad", "ok2"]
    )
    progresses = [progress async for progress in triggered.run()]

    assert len(progresses) == 2
    assert progresses[0].total == 3
    assert progresses[0].completed_count == 2  # the "bad" item failed, siblings survived
    assert progresses[0].batch_id == "batch-1"
    assert progresses[1].batch_id == "batch-2"


async def test_inputs_fn_receives_the_fire_ordinal() -> None:
    trigger = IntervalTrigger(interval=0.0, max_fires=3, sleep=_fake_sleep)
    runner = MapAgent(StubAgent(), concurrency=2)
    seen_ordinals: list[int] = []

    def inputs_fn(ordinal: int) -> list[object]:
        seen_ordinals.append(ordinal)
        return [f"item-{ordinal}"]

    triggered = TriggeredBatch(trigger=trigger, map_agent=runner, inputs_fn=inputs_fn)
    progresses = [progress async for progress in triggered.run()]

    assert seen_ordinals == [1, 2, 3]
    assert all(progress.total == 1 for progress in progresses)


async def test_closes_the_trigger_when_the_stream_ends() -> None:
    trigger = RecordingTrigger(fires=2)
    triggered = TriggeredBatch(
        trigger=trigger,
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=lambda o: ["a"],
        owns_trigger=True,
    )

    progresses = [progress async for progress in triggered.run()]

    assert len(progresses) == 2
    assert trigger.closes == 1


async def test_closes_the_trigger_when_the_consumer_abandons_the_generator() -> None:
    trigger = RecordingTrigger(fires=5)
    triggered = TriggeredBatch(
        trigger=trigger,
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=lambda o: ["a"],
        owns_trigger=True,
    )

    runs = triggered.run()
    await anext(runs)
    await runs.aclose()

    assert trigger.closes == 1


async def test_a_failing_close_does_not_sink_the_run() -> None:
    trigger = RecordingTrigger(fires=1, close_error=RuntimeError("close blew up"))
    triggered = TriggeredBatch(
        trigger=trigger,
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=lambda o: ["a"],
        owns_trigger=True,
    )

    progresses = [progress async for progress in triggered.run()]

    assert len(progresses) == 1
    assert trigger.closes == 1


async def test_on_result_observes_every_run() -> None:
    observed: list[tuple[RunRequest, BatchProgress]] = []

    async def on_result(request: RunRequest, progress: BatchProgress) -> None:
        observed.append((request, progress))

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=2),
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=lambda o: ["a"],
        on_result=on_result,
    )
    progresses = [progress async for progress in triggered.run()]

    assert [progress for _request, progress in observed] == progresses
    assert [request.parameters["fire_ordinal"] for request, _progress in observed] == [1, 2]


async def test_on_error_absorbs_a_failed_run_and_the_stream_continues() -> None:
    observed: list[tuple[int, BaseException]] = []

    async def on_error(request: RunRequest, exc: BaseException) -> None:
        observed.append((request.parameters["fire_ordinal"], exc))

    def inputs_fn(ordinal: int) -> list[object]:
        if ordinal == 1:
            raise RuntimeError("could not fetch this fire's inputs")
        return ["a"]

    triggered = TriggeredBatch(
        trigger=RecordingTrigger(fires=3),
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=inputs_fn,
        on_error=on_error,
    )
    progresses = [progress async for progress in triggered.run()]

    assert len(observed) == 1
    assert observed[0][0] == 1
    assert isinstance(observed[0][1], RuntimeError)
    # The failed fire yields nothing; the two that follow still run.
    assert [progress.batch_id for progress in progresses] == ["batch-2", "batch-3"]


async def test_without_on_error_a_failed_run_propagates() -> None:
    trigger = RecordingTrigger(fires=2)

    def inputs_fn(ordinal: int) -> list[object]:
        raise RuntimeError("could not fetch this fire's inputs")

    triggered = TriggeredBatch(
        trigger=trigger,
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=inputs_fn,
        owns_trigger=True,
    )

    with pytest.raises(RuntimeError):
        _ = [progress async for progress in triggered.run()]
    assert trigger.closes == 1


async def test_on_error_never_swallows_cancellation() -> None:
    observed: list[BaseException] = []

    async def on_error(request: RunRequest, exc: BaseException) -> None:
        observed.append(exc)

    def inputs_fn(ordinal: int) -> list[object]:
        raise asyncio.CancelledError

    trigger = RecordingTrigger(fires=2)
    triggered = TriggeredBatch(
        trigger=trigger,
        map_agent=MapAgent(StubAgent(), concurrency=1),
        inputs_fn=inputs_fn,
        owns_trigger=True,
        on_error=on_error,
    )

    with pytest.raises(asyncio.CancelledError):
        _ = [progress async for progress in triggered.run()]
    assert observed == []
    assert trigger.closes == 1


async def test_the_caller_keeps_ownership_of_the_trigger_by_default() -> None:
    """The default must not close a trigger the caller constructed and still holds."""
    trigger = RecordingTrigger(fires=2)
    triggered = TriggeredBatch(
        trigger=trigger, map_agent=MapAgent(StubAgent(), concurrency=1), inputs_fn=lambda o: ["a"]
    )

    progresses = [progress async for progress in triggered.run()]

    assert len(progresses) == 2
    assert trigger.closes == 0


async def test_an_interval_trigger_can_be_reused_across_runs() -> None:
    """A caller-owned trigger re-fires on a second run instead of doing nothing."""
    trigger = IntervalTrigger(interval=0.0, max_fires=2, sleep=_fake_sleep)
    runner = MapAgent(StubAgent(), concurrency=1)

    def make() -> TriggeredBatch:
        return TriggeredBatch(trigger=trigger, map_agent=runner, inputs_fn=lambda o: ["a"])

    first = [progress.batch_id async for progress in make().run()]
    second = [progress.batch_id async for progress in make().run()]

    assert first == ["batch-1", "batch-2"]
    assert second == ["batch-1", "batch-2"]


async def test_reusing_a_closed_event_trigger_fails_fast_and_never_hangs() -> None:
    """A closed event trigger must raise on re-stream, not park on an empty queue.

    ``wait_for`` bounds the test so a regression fails in a second instead of
    wedging the run: the pre-fix behaviour blocked forever in ``queue.get()``
    with the sentinel already consumed.
    """
    trigger = EventTrigger()
    runner = MapAgent(StubAgent(), concurrency=1)

    def make() -> TriggeredBatch:
        return TriggeredBatch(trigger=trigger, map_agent=runner, inputs_fn=lambda o: ["a"])

    await trigger.fire()
    await trigger.close()
    first = [progress.batch_id async for progress in make().run()]

    assert first == ["batch-1"]

    async def second() -> list[str]:
        return [progress.batch_id async for progress in make().run()]

    with pytest.raises(RuntimeError):
        await asyncio.wait_for(second(), timeout=1.0)


def test_validates_constructor_arguments() -> None:
    runner = MapAgent(StubAgent(), concurrency=1)
    trigger = IntervalTrigger(interval=0.0, max_fires=1, sleep=_fake_sleep)
    with pytest.raises(TypeError):
        TriggeredBatch(trigger="nope", map_agent=runner, inputs_fn=lambda o: [])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        TriggeredBatch(trigger=trigger, map_agent="nope", inputs_fn=lambda o: [])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        TriggeredBatch(trigger=trigger, map_agent=runner, inputs_fn=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        TriggeredBatch(trigger=trigger, map_agent=runner, inputs_fn=lambda o: [], batch_id="")
    with pytest.raises(TypeError):
        TriggeredBatch(
            trigger=trigger,
            map_agent=runner,
            inputs_fn=lambda o: [],
            owns_trigger="yes",  # type: ignore[arg-type]
        )
