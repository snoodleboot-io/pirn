"""Unit tests for :class:`S3Store` using a stub boto3-like client.

The stub mirrors the small slice of the boto3 S3 client surface the store
calls. Real-AWS integration tests live under ``tests/integration`` behind
the ``needs_s3`` marker.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.connectors.object_storage.s3_config import S3Config
from pirn.domains.connectors.object_storage.s3_store import S3Store


# ─────────────────────────────────────────────────────────── stub client


class _StreamBody:
    """Mimics the streaming body returned by boto3's ``get_object``."""

    def __init__(self, data: bytes) -> None:
        self._buf = data
        self._closed = False

    async def read(self, n: int) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk

    def close(self) -> None:
        self._closed = True


class StubS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self.calls.append(("get", {"Bucket": Bucket, "Key": Key}))
        if (Bucket, Key) not in self.objects:
            raise FileNotFoundError(f"s3://{Bucket}/{Key}: no such key")
        return {"Body": _StreamBody(self.objects[(Bucket, Key)])}

    async def put_object(
        self, *, Bucket: str, Key: str, Body: bytes
    ) -> dict[str, Any]:
        self.calls.append(("put", {"Bucket": Bucket, "Key": Key, "size": len(Body)}))
        self.objects[(Bucket, Key)] = Body
        return {"ETag": '"stub"'}

    async def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self.calls.append(("delete", {"Bucket": Bucket, "Key": Key}))
        self.objects.pop((Bucket, Key), None)
        return {}

    async def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str = "",
        ContinuationToken: str | None = None,
    ) -> dict[str, Any]:
        keys = sorted(k for (b, k) in self.objects if b == Bucket and k.startswith(Prefix))
        return {
            "Contents": [{"Key": k} for k in keys],
            "IsTruncated": False,
        }


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
def stub() -> StubS3Client:
    return StubS3Client()


@pytest.fixture
def store(stub: StubS3Client) -> S3Store:
    return S3Store(S3Config(bucket="my-bucket", chunk_size=4), client=stub)


# ────────────────────────────────────────────────────────── conformance


def test_implements_object_store(stub: StubS3Client) -> None:
    store = S3Store(S3Config(bucket="b"), client=stub)
    assert isinstance(store, ObjectStore)


def test_construction_requires_bucket() -> None:
    with pytest.raises(ValueError, match="bucket is required"):
        S3Store(S3Config(bucket=""), client=StubS3Client())


# ───────────────────────────────────────────────────────────── round-trip


@pytest.mark.asyncio
class TestRoundTrip:
    async def test_put_then_get(
        self, store: S3Store, stub: StubS3Client
    ) -> None:
        await store.put("k.bin", b"hello world")
        assert await _drain(await store.get("k.bin")) == b"hello world"

    async def test_streaming_read_uses_chunk_size(
        self, store: S3Store
    ) -> None:
        await store.put("big.bin", b"0123456789ABCDEF")
        chunks: list[bytes] = []
        async for c in await store.get("big.bin"):
            chunks.append(c)
        assert all(len(c) <= 4 for c in chunks)
        assert b"".join(chunks) == b"0123456789ABCDEF"

    async def test_streaming_write_from_iterator(
        self, store: S3Store, stub: StubS3Client
    ) -> None:
        await store.put("stream", _from_chunks([b"a", b"b", b"c"]))
        assert stub.objects[("my-bucket", "stream")] == b"abc"

    async def test_delete_removes_key(
        self, store: S3Store, stub: StubS3Client
    ) -> None:
        await store.put("k", b"x")
        await store.delete("k")
        assert ("my-bucket", "k") not in stub.objects


# ─────────────────────────────────────────────────────────── list / pagination


@pytest.mark.asyncio
class TestList:
    async def test_lists_all_keys_under_prefix(
        self, store: S3Store
    ) -> None:
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")

        keys: list[str] = []
        async for k in await store.list("users/"):
            keys.append(k)
        assert keys == ["users/alice.json", "users/bob.json"]


# ──────────────────────────────────────────────────────────── key validation


@pytest.mark.asyncio
class TestKeyValidation:
    async def test_rejects_empty_key(self, store: S3Store) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await store.put("", b"x")

    async def test_rejects_nul_byte(self, store: S3Store) -> None:
        with pytest.raises(ValueError, match="NUL"):
            await store.put("a\x00b", b"x")

    async def test_rejects_leading_slash(self, store: S3Store) -> None:
        with pytest.raises(ValueError, match="must not start"):
            await store.put("/key", b"x")

    async def test_rejects_dotdot_segment(self, store: S3Store) -> None:
        with pytest.raises(ValueError, match=r"\.\."):
            await store.put("a/../b", b"x")


# ───────────────────────────────────────────────────────────── log safety


class TestLogSafety:
    def test_repr_redacts_secret_access_key(self) -> None:
        cfg = S3Config(
            bucket="b",
            access_key_id="AKIA1234",
            secret_access_key="VERY-SECRET",
            session_token="SESSION-TOKEN",
        )
        text = repr(cfg)
        assert "VERY-SECRET" not in text
        assert "SESSION-TOKEN" not in text
        # Bucket and access key id are not credentials per IAM convention.
        assert "AKIA1234" in text or "<redacted>" in text  # acceptable either way

    def test_audit_dict_redacts_secret(self) -> None:
        cfg = S3Config(bucket="b", secret_access_key="leaked-secret")
        d = cfg.to_audit_dict()
        assert d["secret_access_key"] == "<redacted>"
        assert "leaked-secret" not in str(d)


# ───────────────────────────────────────────────────────────── propagation


@pytest.mark.asyncio
class TestErrorPropagation:
    async def test_get_missing_key_raises(self, store: S3Store) -> None:
        with pytest.raises(FileNotFoundError):
            await _drain(await store.get("nope.txt"))

    async def test_rejects_non_bytes_in_iterator(
        self, store: S3Store
    ) -> None:
        async def bad() -> AsyncIterator[bytes]:
            yield "not bytes"  # type: ignore[misc]

        with pytest.raises(TypeError, match="must yield bytes"):
            await store.put("k", bad())
