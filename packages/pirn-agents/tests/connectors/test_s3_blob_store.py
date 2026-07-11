"""Mirrored tests for :class:`S3BlobStore` with a fake S3 client (F16-S4, S3).

No real cloud or ``aioboto3`` is used: a fake S3 client records multipart uploads,
serves streaming ``get_object`` bodies, and paginates ``list_objects_v2``. The
friendly missing-``aioboto3`` error is forced via ``patch.dict(sys.modules, ...)``.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest import mock

import pytest

from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.connectors.s3_blob_store import S3BlobStore


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def iter_chunks(self, chunk_size: int) -> AsyncIterator[bytes]:
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start : start + chunk_size]


class _FakeS3Client:
    """Records multipart parts, serves get_object, paginates list_objects_v2."""

    def __init__(
        self, *, objects: dict[str, bytes] | None = None, pages: list[dict[str, Any]] | None = None
    ):
        self._objects = objects or {}
        self._pages = pages or []
        self.parts: list[tuple[int, bytes]] = []
        self.completed: list[dict[str, Any]] | None = None
        self.aborted = False

    async def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": _FakeBody(self._objects[Key])}

    async def create_multipart_upload(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"UploadId": "upload-1"}

    async def upload_part(
        self, *, Bucket: str, Key: str, UploadId: str, PartNumber: int, Body: bytes
    ) -> dict[str, Any]:
        self.parts.append((PartNumber, Body))
        return {"ETag": f"etag-{PartNumber}"}

    async def complete_multipart_upload(
        self, *, Bucket: str, Key: str, UploadId: str, MultipartUpload: dict[str, Any]
    ) -> dict[str, Any]:
        self.completed = MultipartUpload["Parts"]
        return {}

    async def abort_multipart_upload(self, *, Bucket: str, Key: str, UploadId: str) -> None:
        self.aborted = True

    async def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        token = kwargs.get("ContinuationToken")
        index = 0 if token is None else int(token)
        return self._pages[index]


class TestS3BlobStorePut:
    async def test_multipart_put_flushes_parts_by_part_size(self) -> None:
        client = _FakeS3Client()
        store = S3BlobStore(bucket="b", client=client, part_size=4)
        await store.put("k", _stream(b"aaaa", b"bbbb", b"cc"))
        # 10 bytes with 4-byte parts -> parts of 4, 4, 2.
        assert [len(body) for _, body in client.parts] == [4, 4, 2]
        assert client.parts[0] == (1, b"aaaa")
        assert client.completed == [
            {"ETag": "etag-1", "PartNumber": 1},
            {"ETag": "etag-2", "PartNumber": 2},
            {"ETag": "etag-3", "PartNumber": 3},
        ]

    async def test_empty_object_uploads_single_part(self) -> None:
        client = _FakeS3Client()
        store = S3BlobStore(bucket="b", client=client, part_size=4)
        await store.put("k", _stream())
        assert client.parts == [(1, b"")]
        assert client.completed == [{"ETag": "etag-1", "PartNumber": 1}]

    async def test_put_aborts_on_error(self) -> None:
        async def _boom() -> AsyncIterator[bytes]:
            yield b"ok"
            raise RuntimeError("stream failed")

        client = _FakeS3Client()
        store = S3BlobStore(bucket="b", client=client, part_size=4)
        with pytest.raises(RuntimeError, match="stream failed"):
            await store.put("k", _boom())
        assert client.aborted is True


class TestS3BlobStoreGetList:
    async def test_get_streams_body_in_chunks(self) -> None:
        client = _FakeS3Client(objects={"k": b"hello world"})
        store = S3BlobStore(bucket="b", client=client, chunk_size=5)
        chunks = [chunk async for chunk in store.get("k")]
        assert chunks == [b"hello", b" worl", b"d"]

    async def test_list_follows_pagination(self) -> None:
        pages = [
            {
                "Contents": [{"Key": "a"}, {"Key": "b"}],
                "IsTruncated": True,
                "NextContinuationToken": "1",
            },
            {"Contents": [{"Key": "c"}], "IsTruncated": False},
        ]
        store = S3BlobStore(bucket="b", client=_FakeS3Client(pages=pages))
        assert await store.list("") == ["a", "b", "c"]


class TestS3BlobStoreConfig:
    def test_is_a_blob_store(self) -> None:
        assert isinstance(S3BlobStore(bucket="b", client=_FakeS3Client()), BlobStore)

    def test_rejects_empty_bucket(self) -> None:
        with pytest.raises(ValueError, match="bucket"):
            S3BlobStore(bucket="")

    def test_rejects_non_positive_part_size(self) -> None:
        with pytest.raises(ValueError, match="part_size"):
            S3BlobStore(bucket="b", part_size=0)

    async def test_missing_aioboto3_raises_friendly_error(self) -> None:
        store = S3BlobStore(bucket="b")
        with mock.patch.dict(sys.modules, {"aioboto3": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[s3\]"'):
                await store.list("")

    async def test_injected_client_close_is_safe_noop(self) -> None:
        store = S3BlobStore(bucket="b", client=_FakeS3Client())
        await store.close()  # injected client has no context manager to exit
        assert store._client is None
