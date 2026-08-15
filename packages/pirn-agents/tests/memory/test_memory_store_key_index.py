"""Tests for :class:`MemoryStoreKeyIndex` (PIR-720).

The index exists because core's ``DataStore`` cannot enumerate its keys, so an
agent store that needs to list what it holds must persist that list itself. The
semantic tests below run against a dict double (fast, and it records every write
so "this was a no-op" is checkable). The concurrency tests run against a shipped
``LocalDiskDataStore``, whose ``asyncio.to_thread`` file IO is a real suspension
point — without one, coroutines run to completion and the read-modify-write
window the lock exists to close never opens.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pirn.backends._signer import _Signer
from pirn.backends.disk import LocalDiskDataStore

from pirn_agents.memory.stores.data_store_memory_store import DataStoreMemoryStore
from pirn_agents.memory.stores.memory_store_key_index import MemoryStoreKeyIndex
from tests.sessions.conftest import DictMemoryStore


@pytest.fixture
def backend() -> DictMemoryStore:
    return DictMemoryStore()


@pytest.fixture
def index(backend: DictMemoryStore) -> MemoryStoreKeyIndex:
    return MemoryStoreKeyIndex(store=backend, index_key="ns:__index__")


def _suspending_index(root: Path, *, index_key: str = "ns:__index__") -> MemoryStoreKeyIndex:
    """An index over a backend that really awaits IO between read and write."""
    disk = LocalDiskDataStore(root, signer=_Signer.test_signer())
    return MemoryStoreKeyIndex(store=DataStoreMemoryStore(data_store=disk), index_key=index_key)


class _RendezvousMemoryStore(DictMemoryStore):
    """A dict store that holds each reader until ``parties`` of them have arrived.

    :class:`TestLockScopeIsHonest` needs both index instances to have read the
    same stale list *before* either writes; only that ordering guarantees one
    edit is clobbered. Raced against real disk IO the ordering merely *happens
    sometimes*: the disk-backed version of that test failed 17 of 50 isolated
    runs, reddening unrelated work. Parking each read on a barrier makes the
    interleaving the test's choice rather than the scheduler's, so the lost
    update is forced rather than hoped for.
    """

    def __init__(self, *, parties: int) -> None:
        super().__init__()
        self._barrier: asyncio.Barrier | None = asyncio.Barrier(parties)

    def stop_rendezvous(self) -> None:
        """Let later reads through unblocked, so assertions can read the record back."""
        self._barrier = None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        found = await super().retrieve(key)
        if self._barrier is not None:
            await self._barrier.wait()
        return found


class TestConstruction:
    def test_rejects_non_store(self) -> None:
        with pytest.raises(TypeError):
            MemoryStoreKeyIndex(store="bad", index_key="k")  # type: ignore[arg-type]

    def test_rejects_empty_index_key(self, backend: DictMemoryStore) -> None:
        with pytest.raises(ValueError):
            MemoryStoreKeyIndex(store=backend, index_key="")

    def test_rejects_empty_field(self, backend: DictMemoryStore) -> None:
        with pytest.raises(ValueError):
            MemoryStoreKeyIndex(store=backend, index_key="k", field="")

    def test_exposes_index_key_and_field(self, backend: DictMemoryStore) -> None:
        built = MemoryStoreKeyIndex(store=backend, index_key="k", field="session_ids")
        assert built.index_key == "k"
        assert built.field == "session_ids"


class TestKeySetSemantics:
    async def test_empty_before_anything_is_written(self, index: MemoryStoreKeyIndex) -> None:
        assert await index.keys() == []

    async def test_add_then_keys_round_trips(self, index: MemoryStoreKeyIndex) -> None:
        await index.add("a")
        assert await index.keys() == ["a"]

    async def test_preserves_insertion_order(self, index: MemoryStoreKeyIndex) -> None:
        for key in ("c", "a", "b"):
            await index.add(key)
        assert await index.keys() == ["c", "a", "b"]

    async def test_add_is_idempotent(self, index: MemoryStoreKeyIndex) -> None:
        await index.add("a")
        await index.add("a")
        assert await index.keys() == ["a"]

    async def test_duplicate_add_writes_nothing(
        self, backend: DictMemoryStore, index: MemoryStoreKeyIndex
    ) -> None:
        await index.add("a")
        writes = len(backend.stored)
        await index.add("a")
        assert len(backend.stored) == writes

    async def test_remove_drops_the_key(self, index: MemoryStoreKeyIndex) -> None:
        await index.add("a")
        await index.add("b")
        await index.remove("a")
        assert await index.keys() == ["b"]

    async def test_remove_absent_key_writes_nothing(
        self, backend: DictMemoryStore, index: MemoryStoreKeyIndex
    ) -> None:
        await index.add("a")
        writes = len(backend.stored)
        await index.remove("ghost")
        assert len(backend.stored) == writes
        assert await index.keys() == ["a"]

    async def test_keys_returns_a_detached_list(self, index: MemoryStoreKeyIndex) -> None:
        await index.add("a")
        got = await index.keys()
        got.append("mutated")
        assert await index.keys() == ["a"]


class TestRecordShape:
    async def test_writes_under_the_configured_field(self, backend: DictMemoryStore) -> None:
        index = MemoryStoreKeyIndex(store=backend, index_key="ns:__index__", field="session_ids")
        await index.add("a")
        assert backend.data["ns:__index__"] == {"session_ids": ["a"]}

    async def test_reads_an_index_written_by_a_prior_instance(
        self, backend: DictMemoryStore
    ) -> None:
        # A durable backend outlives any single index instance.
        await MemoryStoreKeyIndex(store=backend, index_key="ns:__index__").add("a")
        reopened = MemoryStoreKeyIndex(store=backend, index_key="ns:__index__")
        assert await reopened.keys() == ["a"]

    async def test_record_missing_the_field_reads_empty(self, backend: DictMemoryStore) -> None:
        # An index is derived state; a foreign or truncated record must not
        # crash enumeration.
        await backend.store("ns:__index__", {"unrelated": 1})
        index = MemoryStoreKeyIndex(store=backend, index_key="ns:__index__")
        assert await index.keys() == []

    async def test_separate_index_keys_do_not_collide(self, backend: DictMemoryStore) -> None:
        first = MemoryStoreKeyIndex(store=backend, index_key="a:__index__")
        second = MemoryStoreKeyIndex(store=backend, index_key="b:__index__")
        await first.add("x")
        await second.add("y")
        assert await first.keys() == ["x"]
        assert await second.keys() == ["y"]


class TestConcurrentMutation:
    async def test_concurrent_adds_all_survive(self, tmp_path: Path) -> None:
        index = _suspending_index(tmp_path)
        expected = [f"k{i}" for i in range(16)]

        await asyncio.gather(*(index.add(key) for key in expected))

        assert sorted(await index.keys()) == sorted(expected)

    async def test_concurrent_removes_all_apply(self, tmp_path: Path) -> None:
        index = _suspending_index(tmp_path)
        keys = [f"k{i}" for i in range(8)]
        for key in keys:
            await index.add(key)

        await asyncio.gather(*(index.remove(key) for key in keys[:4]))

        assert sorted(await index.keys()) == sorted(keys[4:])

    async def test_interleaved_adds_and_removes_settle_correctly(self, tmp_path: Path) -> None:
        index = _suspending_index(tmp_path)
        for key in ("old0", "old1"):
            await index.add(key)

        await asyncio.gather(
            index.add("new0"),
            index.remove("old0"),
            index.add("new1"),
            index.remove("old1"),
        )

        assert sorted(await index.keys()) == ["new0", "new1"]

    async def test_concurrent_adds_of_the_same_key_store_it_once(self, tmp_path: Path) -> None:
        index = _suspending_index(tmp_path)

        await asyncio.gather(*(index.add("same") for _ in range(8)))

        assert await index.keys() == ["same"]


class TestLockScopeIsHonest:
    async def test_two_instances_over_one_record_lose_an_edit(self) -> None:
        # Pinned deliberately. Each instance owns its own asyncio.Lock, so two of
        # them sharing a record serialise nothing — exactly as the class docstring
        # says. This is the boundary of the guarantee, and it stands in for the
        # multi-process case the lock also cannot cover. Anyone who makes this
        # test fail has strengthened the contract and should update the docstring
        # rather than delete the test; anyone tempted to claim cross-process
        # safety should read it first.
        #
        # The interleaving is driven, not raced: _RendezvousMemoryStore holds both
        # reads until both have arrived, so both instances necessarily see the same
        # stale list and the second write necessarily clobbers the first.
        backend = _RendezvousMemoryStore(parties=2)
        first = MemoryStoreKeyIndex(store=backend, index_key="ns:__index__")
        second = MemoryStoreKeyIndex(store=backend, index_key="ns:__index__")

        try:
            async with asyncio.timeout(5):
                await asyncio.gather(first.add("from-first"), second.add("from-second"))
        except TimeoutError:
            pytest.fail(
                "The two index instances no longer read concurrently, so the lock now "
                "covers more than one instance. That is a stronger contract than "
                "MemoryStoreKeyIndex documents: update the class docstring and this "
                "test together rather than reverting the change."
            )
        backend.stop_rendezvous()

        # Both adds wrote; the later write overwrote the earlier one's key.
        assert backend.stored == ["ns:__index__", "ns:__index__"]
        survivors = await first.keys()
        assert len(survivors) == 1
        # Which of the two survives depends on the order the barrier releases its
        # waiters, so only the *loss* is asserted — that part is guaranteed.
        assert survivors[0] in {"from-first", "from-second"}
