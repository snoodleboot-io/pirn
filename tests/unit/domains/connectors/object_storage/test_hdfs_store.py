"""Unit tests for :class:`HDFSStore` using a stub HDFS client."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.connectors.object_storage.hdfs_config import HDFSConfig
from pirn.domains.connectors.object_storage.hdfs_store import HDFSStore


# ─────────────────────────────────────────────────────────── stub client


class StubHDFSClient:
    def __init__(self, base_path: str = "/data") -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []
        self._base = base_path

    async def get(self, path: str) -> bytes:
        self.calls.append(("get", path))
        if path not in self.objects:
            raise FileNotFoundError(f"hdfs:{path}: no such file")
        return self.objects[path]

    async def put(self, path: str, data: bytes) -> None:
        self.calls.append(("put", path))
        self.objects[path] = data

    async def delete(self, path: str) -> None:
        self.calls.append(("delete", path))
        self.objects.pop(path, None)

    async def list(self, path: str) -> list[str]:
        self.calls.append(("list", path))
        return sorted(k for k in self.objects if k.startswith(path))

    def close(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────── helpers


async def _drain(it: AsyncIterator[bytes]) -> bytes:
    chunks: list[bytes] = []
    async for c in it:
        chunks.append(c)
    return b"".join(chunks)


async def _from_chunks(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for c in chunks:
        yield c


# ─────────────────────────────────────────────────────────────── fixtures


@pytest.fixture
def stub() -> StubHDFSClient:
    return StubHDFSClient(base_path="/data")


@pytest.fixture
def store(stub: StubHDFSClient) -> HDFSStore:
    cfg = HDFSConfig(
        namenode_host="namenode.local",
        namenode_port=50070,
        base_path="/data",
        chunk_size=4,
    )
    return HDFSStore(cfg, client=stub)


# ────────────────────────────────────────────────────────── conformance


def test_implements_object_store(stub: StubHDFSClient) -> None:
    store = HDFSStore(
        HDFSConfig(namenode_host="h", namenode_port=50070),
        client=stub,
    )
    assert isinstance(store, ObjectStore)


def test_construction_requires_namenode_host() -> None:
    with pytest.raises(ValueError, match="namenode_host is required"):
        HDFSStore(HDFSConfig(namenode_host="", namenode_port=50070))


def test_construction_requires_positive_port() -> None:
    with pytest.raises(ValueError, match="namenode_port"):
        HDFSStore(HDFSConfig(namenode_host="h", namenode_port=0))


# ───────────────────────────────────────────────────────────── round-trip


@pytest.mark.asyncio
class TestRoundTrip:
    async def test_put_then_get(self, store: HDFSStore, stub: StubHDFSClient) -> None:
        await store.put("hello.bin", b"hello world")
        assert await _drain(await store.get("hello.bin")) == b"hello world"

    async def test_streaming_read_uses_chunk_size(self, store: HDFSStore) -> None:
        await store.put("big.bin", b"0123456789ABCDEF")
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_iterator(
        self, store: HDFSStore, stub: StubHDFSClient
    ) -> None:
        await store.put("stream", _from_chunks([b"a", b"b", b"c"]))
        assert stub.objects["/data/stream"] == b"abc"

    async def test_delete_removes_key(
        self, store: HDFSStore, stub: StubHDFSClient
    ) -> None:
        await store.put("k", b"x")
        await store.delete("k")
        assert "/data/k" not in stub.objects


# ─────────────────────────────────────────────────────────── list


@pytest.mark.asyncio
class TestList:
    async def test_lists_keys_under_prefix(self, store: HDFSStore) -> None:
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")
        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert all(k.startswith("users/") for k in keys)
        assert len(keys) == 2


# ──────────────────────────────────────────────────────────── key validation


@pytest.mark.asyncio
class TestKeyValidation:
    async def test_rejects_empty_key(self, store: HDFSStore) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self, store: HDFSStore) -> None:
        with pytest.raises(ValueError, match="NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_leading_slash(self, store: HDFSStore) -> None:
        with pytest.raises(ValueError, match="must not start"):
            await store.put("/key", b"x")

    async def test_rejects_dotdot_segment(self, store: HDFSStore) -> None:
        with pytest.raises(ValueError, match=r"\.\."):
            await store.put("a/../b", b"x")


# ───────────────────────────────────────────────────────────── close


@pytest.mark.asyncio
class TestClose:
    async def test_close_clears_client(self, store: HDFSStore, stub: StubHDFSClient) -> None:
        await store.close()
        assert store._client is None

    async def test_double_close_is_safe(self, store: HDFSStore) -> None:
        await store.close()
        await store.close()

    async def test_get_after_close_raises(self, store: HDFSStore) -> None:
        await store.close()
        with pytest.raises(RuntimeError, match="HDFSStore is closed"):
            await store.get("any.bin")

    async def test_put_after_close_raises(self, store: HDFSStore) -> None:
        await store.close()
        with pytest.raises(RuntimeError, match="HDFSStore is closed"):
            await store.put("any.bin", b"data")

    async def test_delete_after_close_raises(self, store: HDFSStore) -> None:
        await store.close()
        with pytest.raises(RuntimeError, match="HDFSStore is closed"):
            await store.delete("any.bin")


# ───────────────────────────────────────────────────────── type safety


@pytest.mark.asyncio
class TestTypeSafety:
    async def test_rejects_non_bytes_in_iterator(self, store: HDFSStore) -> None:
        async def bad() -> AsyncIterator[bytes]:
            yield "not bytes"  # type: ignore[misc]

        with pytest.raises(TypeError, match="must yield bytes"):
            await store.put("k", bad())

    async def test_get_missing_key_raises(self, store: HDFSStore) -> None:
        with pytest.raises(FileNotFoundError):
            await _drain(await store.get("nope.bin"))


# ─────────────────────────────────────────────── config property


def test_config_property(stub: StubHDFSClient) -> None:
    cfg = HDFSConfig(namenode_host="nn", namenode_port=8020, user="hduser")
    store = HDFSStore(cfg, client=stub)
    assert store.config is cfg
    assert store.config.user == "hduser"
