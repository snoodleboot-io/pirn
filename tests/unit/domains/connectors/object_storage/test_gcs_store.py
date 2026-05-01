"""Unit tests for :class:`GCSStore` using a stub gcloud-aio-storage client.

The stub mirrors the small slice of the gcloud-aio-storage Storage surface
the store calls. Real-GCS integration tests live under ``tests/integration``
behind a marker.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.connectors.object_storage.gcs_config import GCSConfig
from pirn.domains.connectors.object_storage.gcs_store import GCSStore


# ─────────────────────────────────────────────────────────── stub client


class _DownloadStream:
    """Mimics the streaming download object returned by gcloud-aio-storage."""

    def __init__(self, data: bytes) -> None:
        self._buf = data
        self._closed = False

    async def read(self, n: int) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk

    async def close(self) -> None:
        self._closed = True


class StubGCSClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def download_stream(
        self, *, bucket: str, object_name: str
    ) -> _DownloadStream:
        self.calls.append(
            ("download", {"bucket": bucket, "object_name": object_name})
        )
        if (bucket, object_name) not in self.objects:
            raise FileNotFoundError(f"gs://{bucket}/{object_name}: no such object")
        return _DownloadStream(self.objects[(bucket, object_name)])

    async def upload(
        self, *, bucket: str, object_name: str, file_data: bytes
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "upload",
                {
                    "bucket": bucket,
                    "object_name": object_name,
                    "size": len(file_data),
                },
            )
        )
        self.objects[(bucket, object_name)] = file_data
        return {"name": object_name}

    async def delete(self, *, bucket: str, object_name: str) -> None:
        self.calls.append(
            ("delete", {"bucket": bucket, "object_name": object_name})
        )
        self.objects.pop((bucket, object_name), None)

    async def list_objects(
        self, *, bucket: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        params = params or {}
        prefix = params.get("prefix", "")
        page_token = params.get("pageToken")
        all_keys = sorted(
            k for (b, k) in self.objects if b == bucket and k.startswith(prefix)
        )
        # Paginate at 2 items per page so we exercise multi-page logic.
        page_size = 2
        start = int(page_token) if page_token else 0
        page = all_keys[start : start + page_size]
        next_token = (
            str(start + page_size)
            if start + page_size < len(all_keys)
            else None
        )
        result: dict[str, Any] = {"items": [{"name": k} for k in page]}
        if next_token is not None:
            result["nextPageToken"] = next_token
        return result


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
def stub() -> StubGCSClient:
    return StubGCSClient()


@pytest.fixture
def store(stub: StubGCSClient) -> GCSStore:
    return GCSStore(GCSConfig(bucket="my-bucket", chunk_size=4), client=stub)


# ────────────────────────────────────────────────────────── conformance


def test_implements_object_store(stub: StubGCSClient) -> None:
    s = GCSStore(GCSConfig(bucket="b"), client=stub)
    assert isinstance(s, ObjectStore)


def test_construction_requires_bucket() -> None:
    with pytest.raises(ValueError, match="bucket is required"):
        GCSStore(GCSConfig(bucket=None), client=StubGCSClient())
    with pytest.raises(ValueError, match="bucket is required"):
        GCSStore(GCSConfig(bucket=""), client=StubGCSClient())


# ───────────────────────────────────────────────────────────── round-trip


@pytest.mark.asyncio
class TestRoundTrip:
    async def test_put_then_get(
        self, store: GCSStore, stub: StubGCSClient
    ) -> None:
        await store.put("k.bin", b"hello world")
        assert await _drain(await store.get("k.bin")) == b"hello world"

    async def test_streaming_read_uses_chunk_size(
        self, store: GCSStore
    ) -> None:
        await store.put("big.bin", b"0123456789ABCDEF")
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_iterator(
        self, store: GCSStore, stub: StubGCSClient
    ) -> None:
        await store.put("stream", _from_chunks([b"a", b"b", b"c"]))
        assert stub.objects[("my-bucket", "stream")] == b"abc"

    async def test_delete_removes_key(
        self, store: GCSStore, stub: StubGCSClient
    ) -> None:
        await store.put("k", b"x")
        await store.delete("k")
        assert ("my-bucket", "k") not in stub.objects


# ─────────────────────────────────────────────────────────── list / pagination


@pytest.mark.asyncio
class TestList:
    async def test_lists_all_keys_under_prefix(
        self, store: GCSStore
    ) -> None:
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("users/carol.json", b"{}")
        await store.put("orders/1.json", b"{}")

        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert keys == [
            "users/alice.json",
            "users/bob.json",
            "users/carol.json",
        ]

    async def test_paginates_across_pages(
        self, store: GCSStore, stub: StubGCSClient
    ) -> None:
        # Stub uses page_size=2; insert >2 to force a second page.
        await store.put("a", b"1")
        await store.put("b", b"2")
        await store.put("c", b"3")
        await store.put("d", b"4")
        keys: list[str] = []
        async for k in await store.list(""):
            keys.append(k)
        assert keys == ["a", "b", "c", "d"]


# ──────────────────────────────────────────────────────────── key validation


@pytest.mark.asyncio
class TestKeyValidation:
    async def test_rejects_empty_key(self, store: GCSStore) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self, store: GCSStore) -> None:
        with pytest.raises(ValueError, match="NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_leading_slash(self, store: GCSStore) -> None:
        with pytest.raises(ValueError, match="must not start"):
            await store.put("/key", b"x")

    async def test_rejects_dotdot_segment(self, store: GCSStore) -> None:
        with pytest.raises(ValueError, match=r"\.\."):
            await store.put("a/../b", b"x")


# ───────────────────────────────────────────────────────────── log safety


class TestLogSafety:
    def test_repr_redacts_service_account_json(self) -> None:
        cfg = GCSConfig(
            bucket="b",
            service_account_json="/secret/path/sa.json",
            project="my-proj",
        )
        text = repr(cfg)
        assert "/secret/path/sa.json" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_service_account(self) -> None:
        cfg = GCSConfig(bucket="b", service_account_json="/leaked/sa.json")
        d = cfg.to_audit_dict()
        assert d["service_account_json"] == "<redacted>"
        assert "/leaked/sa.json" not in str(d)


# ───────────────────────────────────────────────────────────── propagation


@pytest.mark.asyncio
class TestErrorPropagation:
    async def test_get_missing_key_raises(self, store: GCSStore) -> None:
        with pytest.raises(FileNotFoundError):
            await _drain(await store.get("nope.txt"))

    async def test_rejects_non_bytes_in_iterator(
        self, store: GCSStore
    ) -> None:
        async def bad() -> AsyncIterator[bytes]:
            yield "not bytes"  # type: ignore[misc]

        with pytest.raises(TypeError, match="must yield bytes"):
            await store.put("k", bad())
