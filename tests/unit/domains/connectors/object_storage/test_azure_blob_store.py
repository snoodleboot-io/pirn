"""Unit tests for :class:`AzureBlobStore` using a stub azure-blob client.

The stub mirrors the small slice of the
``azure.storage.blob.aio.BlobServiceClient`` surface the store calls. Real
Azure integration tests live under ``tests/integration`` behind a marker.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.object_storage.azure_blob_config import (
    AzureBlobConfig,
)
from pirn.connectors.object_storage.azure_blob_store import (
    AzureBlobStore,
)
from pirn.connectors.object_store import ObjectStore

# ─────────────────────────────────────────────────────────── stub client


class _Downloader:
    """Mimics the StorageStreamDownloader returned by ``download_blob``."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def chunks(self, chunk_size: int) -> AsyncIterator[bytes]:
        buf = self._data
        while buf:
            yield buf[:chunk_size]
            buf = buf[chunk_size:]


class _StubBlobClient:
    def __init__(self, store: _StubServiceClient, container: str, blob: str) -> None:
        self._store = store
        self._container = container
        self._blob = blob

    async def download_blob(self) -> _Downloader:
        self._store.calls.append(
            ("download", {"container": self._container, "blob": self._blob})
        )
        if (self._container, self._blob) not in self._store.objects:
            raise FileNotFoundError(
                f"azure://{self._container}/{self._blob}: no such blob"
            )
        return _Downloader(self._store.objects[(self._container, self._blob)])

    async def upload_blob(self, data: bytes, *, overwrite: bool = False) -> None:
        self._store.calls.append(
            (
                "upload",
                {
                    "container": self._container,
                    "blob": self._blob,
                    "size": len(data),
                    "overwrite": overwrite,
                },
            )
        )
        if not overwrite and (self._container, self._blob) in self._store.objects:
            raise FileExistsError(self._blob)
        self._store.objects[(self._container, self._blob)] = data

    async def delete_blob(self) -> None:
        self._store.calls.append(
            ("delete", {"container": self._container, "blob": self._blob})
        )
        self._store.objects.pop((self._container, self._blob), None)


class _StubContainerClient:
    def __init__(self, store: _StubServiceClient, container: str) -> None:
        self._store = store
        self._container = container

    async def list_blobs(self, *, name_starts_with: str = "") -> AsyncIterator[dict[str, Any]]:
        keys = sorted(
            k
            for (c, k) in self._store.objects
            if c == self._container and k.startswith(name_starts_with)
        )
        for k in keys:
            yield {"name": k}


class _StubServiceClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_blob_client(self, *, container: str, blob: str) -> _StubBlobClient:
        return _StubBlobClient(self, container, blob)

    def get_container_client(self, *, container: str) -> _StubContainerClient:
        return _StubContainerClient(self, container)


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


# ────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_object_store(self) -> None:
        stub = _StubServiceClient()
        s = AzureBlobStore(AzureBlobConfig(container="c"), client=stub)
        assert isinstance(s, ObjectStore)
    
    
    def test_construction_requires_container(self) -> None:
        with self.assertRaisesRegex(ValueError, "container is required"):
            AzureBlobStore(AzureBlobConfig(container=None), client=_StubServiceClient())
        with self.assertRaisesRegex(ValueError, "container is required"):
            AzureBlobStore(AzureBlobConfig(container=""), client=_StubServiceClient())
    
    
    def test_construction_requires_credentials_when_no_client(self) -> None:
        with self.assertRaisesRegex(ValueError, "connection_string or"):
            AzureBlobStore(AzureBlobConfig(container="c"))
    
    
    def test_accepts_connection_string_without_client(self) -> None:
        # Should not raise — credential is supplied via connection_string.
        AzureBlobStore(
            AzureBlobConfig(container="c", connection_string="UseDevelopmentStorage=true"),
            client=_StubServiceClient(),
        )
    
    
    def test_accepts_account_name_and_key_without_client(self) -> None:
        AzureBlobStore(
            AzureBlobConfig(
                container="c", account_name="acct", account_key="abc=="
            ),
            client=_StubServiceClient(),
        )
    
    
# ───────────────────────────────────────────────────────────── round-trip


class TestRoundTrip(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.stub = _StubServiceClient()
        
        
        self.store = AzureBlobStore(
            AzureBlobConfig(container="my-container", chunk_size=4),
            client=self.stub,
        )
        
        
    async def test_put_then_get(self) -> None:
        store = self.store
        stub = self.stub
        await store.put("k.bin", b"hello world")
        assert await _drain(await store.get("k.bin")) == b"hello world"

    async def test_streaming_read_uses_chunk_size(self) -> None:
        store = self.store
        await store.put("big.bin", b"0123456789ABCDEF")
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_iterator(self) -> None:
        store = self.store
        stub = self.stub
        await store.put("stream", _from_chunks([b"a", b"b", b"c"]))
        assert stub.objects[("my-container", "stream")] == b"abc"

    async def test_delete_removes_key(self) -> None:
        store = self.store
        stub = self.stub
        await store.put("k", b"x")
        await store.delete("k")
        assert ("my-container", "k") not in stub.objects


# ─────────────────────────────────────────────────────────── list / pagination


class TestList(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.stub = _StubServiceClient()
        
        
        self.store = AzureBlobStore(
            AzureBlobConfig(container="my-container", chunk_size=4),
            client=self.stub,
        )
        
        
    async def test_lists_all_keys_under_prefix(self) -> None:
        store = self.store
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")

        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert keys == ["users/alice.json", "users/bob.json"]

    async def test_lists_all_when_prefix_empty(self) -> None:
        store = self.store
        await store.put("a", b"1")
        await store.put("b", b"2")
        await store.put("c", b"3")
        keys: list[str] = []
        async for k in await store.list():
            keys.append(k)
        assert keys == ["a", "b", "c"]


# ──────────────────────────────────────────────────────────── key validation


class TestKeyValidation(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.stub = _StubServiceClient()
        
        
        self.store = AzureBlobStore(
            AzureBlobConfig(container="my-container", chunk_size=4),
            client=self.stub,
        )
        
        
    async def test_rejects_empty_key(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_leading_slash(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, "must not start"):
            await store.put("/key", b"x")

    async def test_rejects_dotdot_segment(self) -> None:
        store = self.store
        with self.assertRaisesRegex(ValueError, r"\.\."):
            await store.put("a/../b", b"x")


# ───────────────────────────────────────────────────────────── log safety


class TestLogSafety(unittest.TestCase):
    def test_repr_redacts_account_key_and_connection_string(self) -> None:
        cfg = AzureBlobConfig(
            container="c",
            account_name="acct",
            account_key="VERY-SECRET-KEY",
            connection_string="DefaultEndpointsProtocol=https;AccountKey=LEAKED",
        )
        text = repr(cfg)
        assert "VERY-SECRET-KEY" not in text
        assert "LEAKED" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_secrets(self) -> None:
        cfg = AzureBlobConfig(
            container="c",
            account_key="leaked-key",
            connection_string="leaked-conn",
        )
        d = cfg.to_audit_dict()
        assert d["account_key"] == "<redacted>"
        assert d["connection_string"] == "<redacted>"
        assert "leaked-key" not in str(d)
        assert "leaked-conn" not in str(d)


# ───────────────────────────────────────────────────────────── propagation


class TestErrorPropagation(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.stub = _StubServiceClient()
        
        
        self.store = AzureBlobStore(
            AzureBlobConfig(container="my-container", chunk_size=4),
            client=self.stub,
        )
        
        
    async def test_get_missing_key_raises(self) -> None:
        store = self.store
        with self.assertRaises(FileNotFoundError):
            await _drain(await store.get("nope.txt"))

    async def test_rejects_non_bytes_in_iterator(self) -> None:
        store = self.store
        async def bad() -> AsyncIterator[bytes]:
            yield "not bytes"  # type: ignore[misc]

        with self.assertRaisesRegex(TypeError, "must yield bytes"):
            await store.put("k", bad())
