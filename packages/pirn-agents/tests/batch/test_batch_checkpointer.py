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


def test_scoped_suffixes_cannot_collide_after_escaping() -> None:
    """PIR-813: the suffix -> namespace mapping must be injective.

    Without escaping, ``"2026-08-16"`` and any pair splitting on a hyphen land on
    the same namespace, so two different windows would silently share one
    skip-set. That case stops being hypothetical once a caller names a window
    with a timestamp.
    """
    root = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    assert root.scoped("2026-08-16").batch_id != root.scoped("2026").scoped("08-16").batch_id


def test_scoped_is_injective_across_awkward_suffixes() -> None:
    root = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    suffixes = ["1", "1-2", "1%2D2", "%", "%25", "2026-08-16T00:00", "a-b-c"]
    ids = [root.scoped(s).batch_id for s in suffixes]
    assert len(set(ids)) == len(suffixes)


def test_scoped_still_rejects_an_empty_suffix() -> None:
    root = BatchCheckpointer(store=InMemorySessionStore(), batch_id="daily")
    with pytest.raises(ValueError):
        root.scoped("")
