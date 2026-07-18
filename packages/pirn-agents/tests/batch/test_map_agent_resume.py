"""F28-S3 tests: MapAgent resumable checkpointing over the reused F14 store.

A killed batch resumes from its last checkpoint without re-running completed
items; failed items are left uncheckpointed so a resume retries them.
"""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_checkpointer import BatchCheckpointer
from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.batch.map_agent import MapAgent
from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from tests.batch.batch_doubles import StubAgent


async def _drain(runner: MapAgent, inputs: object) -> list:
    return [result async for result in runner.run(inputs)]  # type: ignore[arg-type]


async def test_checkpoint_persists_completed_keys() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")
    runner = MapAgent(StubAgent(), concurrency=4, checkpointer=checkpointer)

    await _drain(runner, ["a", "b", "c"])

    progress = await checkpointer.load()
    assert progress.completed_keys == frozenset({"0", "1", "2"})


async def test_resume_skips_already_completed_items() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")

    first = StubAgent()
    await _drain(MapAgent(first, concurrency=4, checkpointer=checkpointer), ["a", "b", "c"])

    # Second run over the same inputs: everything is already done.
    second = StubAgent()
    results = await _drain(
        MapAgent(second, concurrency=4, checkpointer=checkpointer), ["a", "b", "c"]
    )

    assert all(r.status is BatchItemStatus.SKIPPED for r in results)
    assert second.calls == []  # the agent is never invoked for completed items


async def test_partial_resume_runs_only_remaining_items() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")
    # Pre-seed: items keyed "0" and "2" already done (by stream index).
    await checkpointer.save(BatchProgress(batch_id="b1", completed_keys=frozenset({"0", "2"})))

    agent = StubAgent()
    results = await _drain(
        MapAgent(agent, concurrency=4, checkpointer=checkpointer), ["a", "b", "c"]
    )

    by_key = {r.key: r for r in results}
    assert by_key["0"].status is BatchItemStatus.SKIPPED
    assert by_key["2"].status is BatchItemStatus.SKIPPED
    assert by_key["1"].status is BatchItemStatus.OK
    assert agent.calls == ["b"]  # only the one uncompleted item ran


async def test_failed_items_are_not_checkpointed_and_retry_on_resume() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")

    # First pass: item "bad" (index 1) fails permanently, the others succeed.
    first = StubAgent(fail_items={"bad"})
    await _drain(MapAgent(first, concurrency=4, checkpointer=checkpointer), ["a", "bad", "c"])

    progress = await checkpointer.load()
    assert progress.completed_keys == frozenset({"0", "2"})  # failed item not recorded

    # Resume: the previously-failed item re-runs (now succeeds); others skip.
    second = StubAgent()
    results = await _drain(
        MapAgent(second, concurrency=4, checkpointer=checkpointer), ["a", "bad", "c"]
    )
    by_key = {r.key: r for r in results}
    assert by_key["1"].status is BatchItemStatus.OK
    assert second.calls == ["bad"]


async def test_checkpoint_every_batches_writes() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")
    runner = MapAgent(StubAgent(), concurrency=1, checkpointer=checkpointer, checkpoint_every=3)

    await _drain(runner, ["a", "b", "c", "d", "e"])

    # Final flush guarantees every completed key is durable regardless of batching.
    progress = await checkpointer.load()
    assert progress.completed_count == 5


def test_rejects_wrong_checkpointer_type() -> None:
    with pytest.raises(TypeError):
        MapAgent(StubAgent(), checkpointer="nope")  # type: ignore[arg-type]


def test_rejects_bad_checkpoint_every() -> None:
    with pytest.raises(ValueError):
        MapAgent(StubAgent(), checkpoint_every=0)
