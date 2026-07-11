"""Mirrored tests for :class:`LocalBlobStore` against a temp dir (F16-S4, local).

Uses a real temporary directory (no cloud): streaming put/get roundtrips, prefix
listing, nested-key creation, and traversal/escape rejection are all covered.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.connectors.local_blob_store import LocalBlobStore


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def _collect(store: BlobStore, key: str) -> bytes:
    out = bytearray()
    async for chunk in store.get(key):
        out.extend(chunk)
    return bytes(out)


class TestLocalBlobStore:
    async def test_put_then_get_roundtrip_streaming(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path, chunk_size=4)
        await store.put("a.txt", _stream(b"hello ", b"world"))
        assert await _collect(store, "a.txt") == b"hello world"

    async def test_put_creates_nested_parents(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        await store.put("nested/dir/obj.bin", _stream(b"data"))
        assert (tmp_path / "nested" / "dir" / "obj.bin").read_bytes() == b"data"

    async def test_list_returns_sorted_keys_under_prefix(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        await store.put("docs/a.txt", _stream(b"1"))
        await store.put("docs/b.txt", _stream(b"2"))
        await store.put("other/c.txt", _stream(b"3"))
        assert await store.list("docs/") == ["docs/a.txt", "docs/b.txt"]
        assert await store.list() == ["docs/a.txt", "docs/b.txt", "other/c.txt"]

    async def test_get_missing_key_raises(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        with pytest.raises(ValueError, match="does not exist"):
            await _collect(store, "missing.txt")

    async def test_put_rejects_absolute_key(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        with pytest.raises(ValueError, match="absolute"):
            await store.put("/etc/passwd", _stream(b"x"))

    async def test_put_rejects_traversal(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            await store.put("../escape.txt", _stream(b"x"))

    async def test_get_rejects_traversal(self, tmp_path: Path) -> None:
        store = LocalBlobStore(root=tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            await _collect(store, "../../etc/passwd")

    def test_is_a_blob_store(self, tmp_path: Path) -> None:
        assert isinstance(LocalBlobStore(root=tmp_path), BlobStore)

    def test_rejects_non_positive_chunk_size(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            LocalBlobStore(root=tmp_path, chunk_size=0)
