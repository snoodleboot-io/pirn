"""Mirrored contract tests for the S2 ``SessionStore`` adapters (PIR-359).

The same interface-contract suite runs against both the in-memory adapter and the
persisted adapter (over a backend-free dict :class:`MemoryStore`), so both are
proven to satisfy the identical save/load/delete/list contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.persisted_session_store import PersistedSessionStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.session_store import SessionStore
from tests.sessions.conftest import DictMemoryStore, make_run_state

StoreFactory = Callable[[], SessionStore]


def _in_memory() -> SessionStore:
    return InMemorySessionStore()


def _persisted() -> SessionStore:
    return PersistedSessionStore(store=DictMemoryStore())


@pytest.fixture(params=[_in_memory, _persisted], ids=["in_memory", "persisted"])
def store(request: pytest.FixtureRequest) -> SessionStore:
    factory: StoreFactory = request.param
    return factory()


class TestSessionStoreContract:
    async def test_save_then_load_round_trips(self, store: SessionStore) -> None:
        cp = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a",)))
        await store.save("s1", cp)
        assert await store.load("s1") == cp

    async def test_load_missing_returns_none(self, store: SessionStore) -> None:
        assert await store.load("nope") is None

    async def test_delete_removes(self, store: SessionStore) -> None:
        cp = RunCheckpoint.create(make_run_state(session_id="s1"))
        await store.save("s1", cp)
        await store.delete("s1")
        assert await store.load("s1") is None

    async def test_delete_missing_is_noop(self, store: SessionStore) -> None:
        await store.delete("ghost")  # must not raise

    async def test_save_overwrites_latest(self, store: SessionStore) -> None:
        first = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a",)))
        second = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a", "b")))
        await store.save("s1", first)
        await store.save("s1", second)
        assert await store.load("s1") == second

    async def test_list_sessions_tracks_live_ids(self, store: SessionStore) -> None:
        await store.save("s1", RunCheckpoint.create(make_run_state(session_id="s1")))
        await store.save("s2", RunCheckpoint.create(make_run_state(session_id="s2")))
        assert list(await store.list_sessions()) == ["s1", "s2"]
        await store.delete("s1")
        assert list(await store.list_sessions()) == ["s2"]

    async def test_save_rejects_non_checkpoint(self, store: SessionStore) -> None:
        with pytest.raises(TypeError):
            await store.save("s1", "bad")  # type: ignore[arg-type]


class TestPersistedAdapterBackendNeutral:
    async def test_survives_new_adapter_over_same_backend(self) -> None:
        # A durable backend outlives any single adapter instance: a fresh
        # PersistedSessionStore over the same MemoryStore re-reads prior state,
        # standing in for a process restart against a persisted backend.
        backend = DictMemoryStore()
        cp = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a", "b")))
        await PersistedSessionStore(store=backend).save("s1", cp)

        reopened = PersistedSessionStore(store=backend)
        assert await reopened.load("s1") == cp
        assert list(await reopened.list_sessions()) == ["s1"]

    async def test_rejects_non_store(self) -> None:
        with pytest.raises(TypeError):
            PersistedSessionStore(store="bad")  # type: ignore[arg-type]

    async def test_default_import_stays_backend_free(self) -> None:
        # Constructing the adapter imports no vendor driver; the backing store
        # (injected) owns any lazy backend import.
        adapter = PersistedSessionStore(store=DictMemoryStore())
        closed: Awaitable[None] = adapter.close()
        await closed  # no backend needed to construct or close
