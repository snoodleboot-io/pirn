"""Unit tests for :class:`LocalFilesystemStore`.

Covers:
- Round-trip put → list → get → delete
- Streaming reads (chunks bound to ``chunk_size``)
- Streaming writes from an async iterator
- Path-traversal rejection (security bar)
- NUL-byte / absolute-path / empty-key rejection
- Idempotent delete
- Protocol conformance
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import pytest

from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.domains.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)


# ───────────────────────────────────────────────────────────── helpers


async def _drain(it: AsyncIterator[bytes]) -> bytes:
    chunks: list[bytes] = []
    async for c in it:
        chunks.append(c)
    return b"".join(chunks)


async def _from_chunks(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for c in chunks:
        yield c


# ───────────────────────────────────────────────────────────── fixtures


@pytest.fixture
def store(tmp_path: Path) -> LocalFilesystemStore:
    cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
    return LocalFilesystemStore(cfg)


# ─────────────────────────────────────────────────────────── conformance


class TestProtocolConformance:
    def test_implements_object_store_protocol(self, store: LocalFilesystemStore) -> None:
        assert isinstance(store, ObjectStore)


# ────────────────────────────────────────────────────────────── put + get


@pytest.mark.asyncio
class TestPutGet:
    async def test_roundtrip_bytes(self, store: LocalFilesystemStore) -> None:
        await store.put("a.txt", b"hello world")
        assert await _drain(await store.get("a.txt")) == b"hello world"

    async def test_creates_parent_directories(self, store: LocalFilesystemStore) -> None:
        await store.put("nested/dir/file.bin", b"abc")
        assert await _drain(await store.get("nested/dir/file.bin")) == b"abc"

    async def test_streaming_read_uses_configured_chunk_size(
        self, tmp_path: Path
    ) -> None:
        cfg = LocalFilesystemConfig(root=tmp_path, chunk_size=4)
        store = LocalFilesystemStore(cfg)
        await store.put("big.bin", b"0123456789ABCDEF")  # 16 bytes
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_async_iterator(
        self, store: LocalFilesystemStore
    ) -> None:
        await store.put("stream.bin", _from_chunks([b"alpha", b"beta", b"gamma"]))
        assert await _drain(await store.get("stream.bin")) == b"alphabetagamma"

    async def test_overwrite_replaces_content(
        self, store: LocalFilesystemStore
    ) -> None:
        await store.put("k", b"first")
        await store.put("k", b"second")
        assert await _drain(await store.get("k")) == b"second"

    async def test_rejects_non_bytes_in_iterator(
        self, store: LocalFilesystemStore
    ) -> None:
        async def bad_iter() -> AsyncIterator[bytes]:
            yield b"ok"
            yield "not bytes"  # type: ignore[misc]

        with pytest.raises(TypeError, match="must yield bytes"):
            await store.put("k", bad_iter())

    async def test_get_missing_raises_filenotfound(
        self, store: LocalFilesystemStore
    ) -> None:
        # The error must surface, not be silently swallowed (fail-loud bar).
        with pytest.raises(FileNotFoundError):
            await _drain(await store.get("does/not/exist.txt"))


# ──────────────────────────────────────────────────────────── path safety


@pytest.mark.asyncio
class TestPathSafety:
    async def test_rejects_absolute_path(self, store: LocalFilesystemStore) -> None:
        with pytest.raises(ValueError, match="absolute"):
            await store.put("/etc/passwd", b"x")

    async def test_rejects_empty_key(self, store: LocalFilesystemStore) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self, store: LocalFilesystemStore) -> None:
        with pytest.raises(ValueError, match="NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_traversal_dotdot(self, store: LocalFilesystemStore) -> None:
        with pytest.raises(PermissionError, match="outside"):
            await store.put("../escape.txt", b"x")

    async def test_rejects_deeper_traversal(
        self, store: LocalFilesystemStore
    ) -> None:
        with pytest.raises(PermissionError, match="outside"):
            await store.put("a/b/../../../escape.txt", b"x")

    async def test_traversal_message_does_not_echo_resolved_absolute_path(
        self, store: LocalFilesystemStore, tmp_path: Path
    ) -> None:
        # The error must not echo the resolved absolute path — that could
        # leak filesystem layout to a caller that supplied a traversal.
        with pytest.raises(PermissionError) as exc_info:
            await store.put("../../../etc/passwd", b"x")
        msg = str(exc_info.value)
        # The user-supplied key is acceptable context; the resolved path is not.
        assert "../../../etc/passwd" in msg
        assert str(tmp_path) not in msg


# ─────────────────────────────────────────────────────────────── delete


@pytest.mark.asyncio
class TestDelete:
    async def test_delete_removes_file(self, store: LocalFilesystemStore) -> None:
        await store.put("x", b"y")
        await store.delete("x")
        with pytest.raises(FileNotFoundError):
            await _drain(await store.get("x"))

    async def test_delete_missing_is_idempotent(
        self, store: LocalFilesystemStore
    ) -> None:
        await store.delete("never-existed")
        await store.delete("never-existed")  # second call must not raise


# ───────────────────────────────────────────────────────────────── list


@pytest.mark.asyncio
class TestList:
    async def test_list_empty_root(self, store: LocalFilesystemStore) -> None:
        keys: list[str] = []
        async for k in await store.list():
            keys.append(k)
        assert keys == []

    async def test_list_returns_lex_sorted_keys(
        self, store: LocalFilesystemStore
    ) -> None:
        await store.put("c.txt", b"")
        await store.put("a.txt", b"")
        await store.put("b/inner.txt", b"")

        keys: list[str] = []
        async for k in await store.list():
            keys.append(k)
        assert keys == ["a.txt", "b/inner.txt", "c.txt"]

    async def test_list_filters_by_prefix(
        self, store: LocalFilesystemStore
    ) -> None:
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")

        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert keys == ["users/alice.json", "users/bob.json"]


# ───────────────────────────────────────────────────────── construction


class TestConstruction:
    def test_creates_root_when_create_root_true(self, tmp_path: Path) -> None:
        root = tmp_path / "fresh"
        assert not root.exists()
        LocalFilesystemStore(LocalFilesystemConfig(root=root, create_root=True))
        assert root.is_dir()

    def test_raises_when_root_missing_and_create_root_false(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "missing"
        with pytest.raises(FileNotFoundError):
            LocalFilesystemStore(
                LocalFilesystemConfig(root=root, create_root=False)
            )
