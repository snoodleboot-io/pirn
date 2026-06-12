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

import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from pirn.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)
from pirn.connectors.object_store import ObjectStore

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


# ─────────────────────────────────────────────────────────── conformance


class TestProtocolConformance(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp_store = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_store.name)
        cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
        self.store = LocalFilesystemStore(cfg)
        
        

    def tearDown(self) -> None:
        self._tmp_store.cleanup()
    def test_implements_object_store_protocol(self) -> None:
        store = self.store
        assert isinstance(store, ObjectStore)


# ────────────────────────────────────────────────────────────── put + get


class TestPutGet(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_store = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_store.name)
        cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
        self.store = LocalFilesystemStore(cfg)
        
        

    async def asyncTearDown(self) -> None:
        self._tmp_store.cleanup()
    async def test_roundtrip_bytes(self) -> None:
        store = self.store
        await store.put("a.txt", b"hello world")
        assert await _drain(await store.get("a.txt")) == b"hello world"

    async def test_creates_parent_directories(self) -> None:
        store = self.store
        await store.put("nested/dir/file.bin", b"abc")
        assert await _drain(await store.get("nested/dir/file.bin")) == b"abc"

    async def test_streaming_read_uses_configured_chunk_size(self) -> None:
        _td_test_streaming_read_uses_configured_chunk_size = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_streaming_read_uses_configured_chunk_size.cleanup)
        tmp_path = Path(_td_test_streaming_read_uses_configured_chunk_size.name)
        cfg = LocalFilesystemConfig(root=tmp_path, chunk_size=4)
        store = LocalFilesystemStore(cfg)
        await store.put("big.bin", b"0123456789ABCDEF")  # 16 bytes
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_async_iterator(self) -> None:
        store = self.store
        await store.put("stream.bin", _from_chunks([b"alpha", b"beta", b"gamma"]))
        assert await _drain(await store.get("stream.bin")) == b"alphabetagamma"

    async def test_overwrite_replaces_content(self) -> None:
        store = self.store
        await store.put("k", b"first")
        await store.put("k", b"second")
        assert await _drain(await store.get("k")) == b"second"

    async def test_rejects_non_bytes_in_iterator(self) -> None:
        store = self.store
        async def bad_iter() -> AsyncIterator[bytes]:
            yield b"ok"
            yield "not bytes"  # type: ignore[misc]

        with self.assertRaisesRegex(TypeError, "must yield bytes"):
            await store.put("k", bad_iter())

    async def test_get_missing_raises_filenotfound(self) -> None:
        store = self.store
        # The error must surface, not be silently swallowed (fail-loud bar).
        with self.assertRaises(FileNotFoundError):
            await _drain(await store.get("does/not/exist.txt"))


# ──────────────────────────────────────────────────────────── path safety


class TestPathSafety(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_store = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_store.name)
        cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
        self.store = LocalFilesystemStore(cfg)
        
        

    async def asyncTearDown(self) -> None:
        self._tmp_store.cleanup()
    async def test_rejects_absolute_path(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "absolute"):
            await store.put("/etc/passwd", b"x")

    async def test_rejects_empty_key(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_traversal_dotdot(self) -> None:
        store = self.store
        with self.assertRaisesRegex(PermissionError, "outside"):
            await store.put("../escape.txt", b"x")

    async def test_rejects_deeper_traversal(self) -> None:
        store = self.store
        with self.assertRaisesRegex(PermissionError, "outside"):
            await store.put("a/b/../../../escape.txt", b"x")

    async def test_traversal_message_does_not_echo_resolved_absolute_path(self) -> None:
        store = self.store
        _td_traversal = tempfile.TemporaryDirectory()
        self.addCleanup(_td_traversal.cleanup)
        tmp_path = Path(_td_traversal.name)
        # The error must not echo the resolved absolute path — that could
        # leak filesystem layout to a caller that supplied a traversal.
        with self.assertRaises(PermissionError) as exc_info:
            await store.put("../../../etc/passwd", b"x")
        msg = str(exc_info.exception)
        # The user-supplied key is acceptable context; the resolved path is not.
        assert "../../../etc/passwd" in msg
        assert str(tmp_path) not in msg


# ─────────────────────────────────────────────────────────────── delete


class TestDelete(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_store = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_store.name)
        cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
        self.store = LocalFilesystemStore(cfg)
        
        

    async def asyncTearDown(self) -> None:
        self._tmp_store.cleanup()
    async def test_delete_removes_file(self) -> None:
        store = self.store
        await store.put("x", b"y")
        await store.delete("x")
        with self.assertRaises(FileNotFoundError):
            await _drain(await store.get("x"))

    async def test_delete_missing_is_idempotent(self) -> None:
        store = self.store
        await store.delete("never-existed")
        await store.delete("never-existed")  # second call must not raise


# ───────────────────────────────────────────────────────────────── list


class TestList(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_store = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_store.name)
        cfg = LocalFilesystemConfig(root=tmp_path / "data", chunk_size=8)
        self.store = LocalFilesystemStore(cfg)
        
        

    async def asyncTearDown(self) -> None:
        self._tmp_store.cleanup()
    async def test_list_empty_root(self) -> None:
        store = self.store
        keys: list[str] = []
        async for k in await store.list():
            keys.append(k)
        assert keys == []

    async def test_list_returns_lex_sorted_keys(self) -> None:
        store = self.store
        await store.put("c.txt", b"")
        await store.put("a.txt", b"")
        await store.put("b/inner.txt", b"")

        keys: list[str] = []
        async for k in await store.list():
            keys.append(k)
        assert keys == ["a.txt", "b/inner.txt", "c.txt"]

    async def test_list_filters_by_prefix(self) -> None:
        store = self.store
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")

        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert keys == ["users/alice.json", "users/bob.json"]


# ───────────────────────────────────────────────────────── construction


class TestConstruction(unittest.TestCase):
    def test_creates_root_when_create_root_true(self) -> None:
        _td_test_creates_root_when_create_root_true = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_creates_root_when_create_root_true.cleanup)
        tmp_path = Path(_td_test_creates_root_when_create_root_true.name)
        root = tmp_path / "fresh"
        assert not root.exists()
        LocalFilesystemStore(LocalFilesystemConfig(root=root, create_root=True))
        assert root.is_dir()

    def test_raises_when_root_missing_and_create_root_false(self) -> None:
        _td_test_raises_when_root_missing_and_create_root_false = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_raises_when_root_missing_and_create_root_false.cleanup)
        tmp_path = Path(_td_test_raises_when_root_missing_and_create_root_false.name)
        root = tmp_path / "missing"
        with self.assertRaises(FileNotFoundError):
            LocalFilesystemStore(
                LocalFilesystemConfig(root=root, create_root=False)
            )
