"""Binding tests for :class:`TriggeredBatch` (F28-S5 / PIR-584).

One batch runs per trigger fire; each run yields a :class:`BatchProgress` whose
``completed_count``/``total`` is the partial-failure report, and ``inputs_fn``
receives the fire ordinal so each run can pull fresh data. Stub doubles keep it
deterministic.
"""

from __future__ import annotations

import pytest

from pirn_agents.batch.interval_trigger import IntervalTrigger
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.batch.triggered_batch import TriggeredBatch
from tests.batch.batch_doubles import StubAgent


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
