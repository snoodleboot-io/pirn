"""Concurrency regression tests for :class:`PersistedSessionStore` (PIR-720).

``PersistedSessionStore`` keeps an ``__index__`` record so :meth:`list_sessions`
does not have to scan the backend, because core's ``DataStore`` is
content-hash-keyed and offers no enumeration. Maintaining that record used to be
a bare read-modify-write: ``save`` stored the checkpoint, *then* read the index,
appended its own id, and wrote the whole list back. Two saves in flight at once
each read the pre-existing list and each wrote their own successor, so the later
write erased the earlier id — the session's checkpoint was still stored and
:meth:`load` still returned it, but it had silently vanished from enumeration.

These tests drive the race through a **shipped** backend rather than a double:
``LocalDiskDataStore`` runs its file IO on ``asyncio.to_thread``, so every
``put``/``get`` is a genuine suspension point at which a concurrent save can
interleave. Any real backend (disk, S3, ValKey, Postgres) awaits I/O the same
way; only the fully synchronous ``InMemoryDataStore`` happens to hide the window.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pirn.backends._signer import _Signer
from pirn.backends.disk import LocalDiskDataStore

from pirn_agents.memory.stores.data_store_memory_store import DataStoreMemoryStore
from pirn_agents.sessions.persisted_session_store import PersistedSessionStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from tests.sessions.conftest import make_run_state


@pytest.fixture
def store(tmp_path: Path) -> PersistedSessionStore:
    """The persisted adapter over a signed disk backend that really suspends."""
    disk = LocalDiskDataStore(tmp_path, signer=_Signer.test_signer())
    return PersistedSessionStore(store=DataStoreMemoryStore(data_store=disk))


def _checkpoint(session_id: str) -> RunCheckpoint:
    return RunCheckpoint.create(make_run_state(session_id=session_id))


class TestConcurrentIndexMaintenance:
    async def test_concurrent_saves_all_reach_the_index(self, store: PersistedSessionStore) -> None:
        expected = [f"s{i}" for i in range(8)]

        await asyncio.gather(*(store.save(sid, _checkpoint(sid)) for sid in expected))

        assert sorted(await store.list_sessions()) == expected

    async def test_concurrent_saves_stay_loadable(self, store: PersistedSessionStore) -> None:
        # The data was never at risk — only enumeration was — so this pins the
        # invariant the index is supposed to mirror: everything listable is
        # loadable, and everything saved is listable.
        session_ids = [f"s{i}" for i in range(8)]

        await asyncio.gather(*(store.save(sid, _checkpoint(sid)) for sid in session_ids))

        listed = list(await store.list_sessions())
        for session_id in session_ids:
            assert await store.load(session_id) is not None
            assert session_id in listed

    async def test_concurrent_deletes_all_leave_the_index(
        self, store: PersistedSessionStore
    ) -> None:
        # delete() ran the same read-modify-write in reverse: concurrent removals
        # each dropped one id from a stale snapshot, resurrecting the others.
        session_ids = [f"s{i}" for i in range(8)]
        for session_id in session_ids:
            await store.save(session_id, _checkpoint(session_id))

        await asyncio.gather(*(store.delete(sid) for sid in session_ids[:4]))

        assert sorted(await store.list_sessions()) == session_ids[4:]

    async def test_concurrent_save_and_delete_do_not_clobber(
        self, store: PersistedSessionStore
    ) -> None:
        # A save racing an unrelated delete: neither may lose the other's edit.
        await store.save("keep", _checkpoint("keep"))
        await store.save("drop", _checkpoint("drop"))

        await asyncio.gather(
            store.save("added", _checkpoint("added")),
            store.delete("drop"),
        )

        assert sorted(await store.list_sessions()) == ["added", "keep"]
