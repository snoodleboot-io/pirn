"""Seam tests for :class:`DataStoreMemoryStore` (PIR-787).

``MemoryStore`` had no plain key-value implementation: its only concrete
subclasses were the ``VectorMemoryStore`` family, whose ``store()`` requires a
``"vector"`` entry.  Every keyed consumer (``PersistedSessionStore``,
``ThreadRepository``, ``MemoryWriter``, …) therefore had no shipped backend to
run against.  These tests exercise the adapter that closes that gap against two
*real* core ``DataStore`` backends — in-memory and local disk — rather than a
hand-rolled double.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pirn.backends._signer import _Signer
from pirn.backends.base.data_store import DataStore
from pirn.backends.disk import LocalDiskDataStore
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore

from pirn_agents.memory.stores.data_store_memory_store import DataStoreMemoryStore
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.sessions.persisted_session_store import PersistedSessionStore
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from tests.sessions.conftest import make_run_state


def _disk_store(root: Path) -> LocalDiskDataStore:
    """A signed disk ``DataStore`` — no security default is relaxed."""
    return LocalDiskDataStore(root, signer=_Signer.test_signer())


@pytest.fixture
def backend() -> InMemoryDataStore:
    return InMemoryDataStore()


@pytest.fixture
def store(backend: InMemoryDataStore) -> DataStoreMemoryStore:
    return DataStoreMemoryStore(data_store=backend)


class TestConstruction:
    def test_is_a_memory_store(self, store: DataStoreMemoryStore) -> None:
        assert isinstance(store, MemoryStore)

    def test_rejects_non_data_store(self) -> None:
        with pytest.raises(TypeError):
            DataStoreMemoryStore(data_store="bad")  # type: ignore[arg-type]

    def test_rejects_empty_namespace(self, backend: InMemoryDataStore) -> None:
        with pytest.raises(ValueError):
            DataStoreMemoryStore(data_store=backend, namespace="")

    def test_exposes_its_namespace(self, backend: InMemoryDataStore) -> None:
        assert DataStoreMemoryStore(data_store=backend, namespace="ns").namespace == "ns"


class TestKeyedSurface:
    async def test_store_then_retrieve_round_trips(self, store: DataStoreMemoryStore) -> None:
        await store.store("k1", {"text": "hello", "score": 1})
        assert await store.retrieve("k1") == {"text": "hello", "score": 1}

    async def test_retrieve_missing_returns_none(self, store: DataStoreMemoryStore) -> None:
        assert await store.retrieve("nope") is None

    async def test_store_overwrites(self, store: DataStoreMemoryStore) -> None:
        await store.store("k1", {"v": 1})
        await store.store("k1", {"v": 2})
        assert await store.retrieve("k1") == {"v": 2}

    async def test_forget_removes(self, store: DataStoreMemoryStore) -> None:
        await store.store("k1", {"v": 1})
        await store.forget("k1")
        assert await store.retrieve("k1") is None

    async def test_forget_missing_is_noop(self, store: DataStoreMemoryStore) -> None:
        await store.forget("ghost")  # must not raise

    async def test_an_evicted_entry_reads_as_absent(self) -> None:
        # Arrange — a bounded backend drops its least recently used entries
        # (PIR-839).  `ValueEvictedError` is a KeyError, so it lands in the
        # same translation as any other absence.
        adapter = DataStoreMemoryStore(data_store=InMemoryDataStore(max_values=2))
        await adapter.store("k1", {"v": 1})
        await adapter.store("k2", {"v": 2})
        await adapter.store("k3", {"v": 3})

        # Act / Assert — a MemoryStore reports absence rather than promising
        # durability, so this is the contract working, not a leak.  A session
        # whose memory must survive needs a durable DataStore.
        assert await adapter.retrieve("k1") is None
        assert await adapter.retrieve("k3") == {"v": 3}

    async def test_stores_a_snapshot_not_a_live_reference(
        self, store: DataStoreMemoryStore
    ) -> None:
        payload = {"v": 1}
        await store.store("k1", payload)
        payload["v"] = 999
        assert await store.retrieve("k1") == {"v": 1}

    async def test_rejects_non_mapping_value(self, store: DataStoreMemoryStore) -> None:
        with pytest.raises(TypeError):
            await store.store("k1", ["not", "a", "mapping"])  # type: ignore[arg-type]

    async def test_accepts_the_plain_mappings_a_vector_store_rejects(
        self, store: DataStoreMemoryStore
    ) -> None:
        # The defect: VectorMemoryStore.store() raises KeyError on any mapping
        # without a "vector" entry.  This adapter must accept it.
        await store.store("session:s1", {"session_ids": ["s1", "s2"]})
        assert await store.retrieve("session:s1") == {"session_ids": ["s1", "s2"]}

    async def test_close_does_not_raise(self, store: DataStoreMemoryStore) -> None:
        await store.close()


class TestSearchIsRefused:
    async def test_search_raises_not_implemented(self, store: DataStoreMemoryStore) -> None:
        with pytest.raises(NotImplementedError) as excinfo:
            await store.search("anything")
        message = str(excinfo.value)
        assert "DataStoreMemoryStore" in message
        assert "vector" in message.lower()


class TestKeyHashing:
    def test_content_hash_is_a_sha256_hex_digest(self, store: DataStoreMemoryStore) -> None:
        digest = store.content_hash("session:s1")
        assert len(digest) == 64
        assert all(char in "0123456789abcdef" for char in digest)

    async def test_backend_never_sees_the_raw_key(
        self, store: DataStoreMemoryStore, backend: InMemoryDataStore
    ) -> None:
        await store.store("session:s1", {"v": 1})
        assert await backend.has("session:s1") is False
        assert await backend.has(store.content_hash("session:s1")) is True

    async def test_hashing_is_stable_across_instances(
        self, backend: InMemoryDataStore, store: DataStoreMemoryStore
    ) -> None:
        await store.store("k1", {"v": 1})
        reopened = DataStoreMemoryStore(data_store=backend)
        assert await reopened.retrieve("k1") == {"v": 1}

    async def test_namespaces_do_not_collide(self, backend: InMemoryDataStore) -> None:
        left = DataStoreMemoryStore(data_store=backend, namespace="left")
        right = DataStoreMemoryStore(data_store=backend, namespace="right")
        await left.store("k1", {"side": "left"})
        await right.store("k1", {"side": "right"})
        assert await left.retrieve("k1") == {"side": "left"}
        assert await right.retrieve("k1") == {"side": "right"}

    @pytest.mark.parametrize(
        "key",
        ["session:s1", "../../etc/passwd", "a/b/c", "with space", "unicode-ключ", "?*<>|"],
        ids=["colon", "traversal", "slashes", "space", "unicode", "wildcards"],
    )
    async def test_filesystem_hostile_keys_round_trip_on_disk(
        self, tmp_path: Path, key: str
    ) -> None:
        store = DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        await store.store(key, {"v": key})
        assert await store.retrieve(key) == {"v": key}


class TestDiskBackend:
    async def test_round_trips_through_a_signed_disk_store(self, tmp_path: Path) -> None:
        store = DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        await store.store("k1", {"v": 1})
        assert await store.retrieve("k1") == {"v": 1}

    async def test_survives_a_fresh_adapter_over_the_same_root(self, tmp_path: Path) -> None:
        await DataStoreMemoryStore(data_store=_disk_store(tmp_path)).store("k1", {"v": 1})
        reopened = DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        assert await reopened.retrieve("k1") == {"v": 1}

    async def test_missing_key_on_disk_returns_none(self, tmp_path: Path) -> None:
        store = DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        assert await store.retrieve("never-written") is None


class TestConsumersNowHaveAShippedBackend:
    """The point of the ticket: keyed consumers run on real core backends."""

    async def test_persisted_session_store_over_in_memory_data_store(self) -> None:
        adapter = PersistedSessionStore(store=DataStoreMemoryStore(data_store=InMemoryDataStore()))
        checkpoint = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a", "b")))
        await adapter.save("s1", checkpoint)
        assert await adapter.load("s1") == checkpoint
        assert list(await adapter.list_sessions()) == ["s1"]

    async def test_persisted_session_store_survives_restart_on_disk(self, tmp_path: Path) -> None:
        checkpoint = RunCheckpoint.create(make_run_state(session_id="s1", plan=("a", "b")))
        await PersistedSessionStore(
            store=DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        ).save("s1", checkpoint)

        reopened = PersistedSessionStore(
            store=DataStoreMemoryStore(data_store=_disk_store(tmp_path))
        )
        assert await reopened.load("s1") == checkpoint
        assert list(await reopened.list_sessions()) == ["s1"]


class TestBackendNeutrality:
    async def test_accepts_any_data_store_subclass(self, tmp_path: Path) -> None:
        for backend in (InMemoryDataStore(), _disk_store(tmp_path)):
            assert isinstance(backend, DataStore)
            adapter = DataStoreMemoryStore(data_store=backend)
            await adapter.store("k", {"v": 1})
            assert await adapter.retrieve("k") == {"v": 1}
