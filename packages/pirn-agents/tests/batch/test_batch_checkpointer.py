"""F28-S3 tests: BatchCheckpointer persists batch progress over an F14 store."""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_checkpointer import BatchCheckpointer
from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint


async def test_load_returns_empty_when_nothing_saved() -> None:
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="b1")
    progress = await checkpointer.load()
    assert progress.batch_id == "b1"
    assert progress.completed_keys == frozenset()


async def test_save_then_load_round_trips_keys() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")
    await checkpointer.save(BatchProgress(batch_id="b1", completed_keys=frozenset({"k1", "k2"})))

    reloaded = await checkpointer.load()
    assert reloaded.completed_keys == frozenset({"k1", "k2"})


async def test_persists_as_f14_run_checkpoint() -> None:
    store = InMemorySessionStore()
    checkpointer = BatchCheckpointer(store=store, batch_id="b1")
    await checkpointer.save(BatchProgress(batch_id="b1", completed_keys=frozenset({"k1"})))

    # The batch checkpoint lives in the F14 store as a real RunCheckpoint.
    checkpoint = await store.load("b1")
    assert isinstance(checkpoint, RunCheckpoint)
    assert checkpoint.state.cursor.completed_steps == ("k1",)


async def test_save_rejects_mismatched_batch_id() -> None:
    checkpointer = BatchCheckpointer(store=InMemorySessionStore(), batch_id="b1")
    with pytest.raises(TypeError):
        await checkpointer.save(BatchProgress(batch_id="other"))


def test_rejects_non_session_store() -> None:
    with pytest.raises(TypeError):
        BatchCheckpointer(store="not-a-store", batch_id="b1")  # type: ignore[arg-type]


def test_rejects_empty_batch_id() -> None:
    with pytest.raises(ValueError):
        BatchCheckpointer(store=InMemorySessionStore(), batch_id="")
