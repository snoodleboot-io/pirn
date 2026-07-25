"""Tests for :class:`StreamingS3Store` with a fake S3 client (PIR-690).

No real cloud or ``aioboto3`` is used: a fake S3 client records multipart uploads,
serves streaming ``get_object`` bodies, and paginates ``list_objects_v2``.

The store subclasses core's :class:`S3Store`, so ``get``/``list``/``delete`` and
the ``_validate_key`` path-traversal guard are inherited and covered here; only
the streaming multipart ``put`` is agents-side behaviour.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from pirn.connectors.object_storage.s3_config import S3Config
from pirn.connectors.object_store import ObjectStore

from pirn_agents.connectors.streaming_s3_store import StreamingS3Store


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class _FakeBody:
    """Matches core S3Store.get's consumption: repeated ``read(chunk_size)``."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._pos = self._data[self._pos :], len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


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
        self.single_put: bytes | None = None

    async def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": _FakeBody(self._objects[Key])}

    async def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> dict[str, Any]:
        self.single_put = Body
        self._objects[Key] = Body
        return {}

    async def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self._objects.pop(Key, None)
        return {}

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


_PART = 5242880  # S3's minimum non-final part size, which the store now enforces.


def _store(client: _FakeS3Client, *, part_size: int = _PART) -> StreamingS3Store:
    return StreamingS3Store(S3Config(bucket="b"), client=client, part_size=part_size)


class TestStreamingMultipartPut:
    async def test_flushes_parts_by_part_size(self) -> None:
        client = _FakeS3Client()
        # 2.5 parts' worth -> two full parts plus a half-sized tail.
        await _store(client).put("k", _stream(b"a" * _PART, b"b" * _PART, b"c" * (_PART // 2)))
        assert [len(body) for _, body in client.parts] == [_PART, _PART, _PART // 2]
        assert client.parts[0][0] == 1
        assert client.completed == [
            {"ETag": "etag-1", "PartNumber": 1},
            {"ETag": "etag-2", "PartNumber": 2},
            {"ETag": "etag-3", "PartNumber": 3},
        ]

    async def test_empty_body_takes_single_put_not_a_zero_byte_part(self) -> None:
        # A 0-byte UploadPart is not reliably accepted by S3; nothing to multipart.
        client = _FakeS3Client()
        await _store(client).put("k", _stream())
        assert client.parts == []
        assert client.single_put == b""

    async def test_body_below_part_size_takes_single_put(self) -> None:
        # Never opens a multipart upload it could not satisfy (sub-minimum part).
        client = _FakeS3Client()
        await _store(client).put("k", _stream(b"small"))
        assert client.parts == []
        assert client.single_put == b"small"
        assert client.aborted is False

    async def test_aborts_started_upload_on_error(self) -> None:
        async def _boom() -> AsyncIterator[bytes]:
            yield b"a" * _PART
            raise RuntimeError("stream failed")

        client = _FakeS3Client()
        with pytest.raises(RuntimeError, match="stream failed"):
            await _store(client).put("k", _boom())
        assert client.aborted is True

    async def test_no_abort_when_no_upload_was_started(self) -> None:
        async def _boom() -> AsyncIterator[bytes]:
            yield b"tiny"
            raise RuntimeError("stream failed")

        client = _FakeS3Client()
        with pytest.raises(RuntimeError, match="stream failed"):
            await _store(client).put("k", _boom())
        assert client.aborted is False

    async def test_rejects_non_bytes_chunk(self) -> None:
        async def _bad() -> AsyncIterator[Any]:
            yield "not bytes"

        client = _FakeS3Client()
        with pytest.raises(TypeError, match="must yield bytes"):
            await _store(client).put("k", _bad())

    async def test_abort_failure_does_not_mask_original_error(self) -> None:
        class _AbortFails(_FakeS3Client):
            async def abort_multipart_upload(self, **_: Any) -> None:
                raise ConnectionError("connection already dead")

        async def _boom() -> AsyncIterator[bytes]:
            yield b"a" * _PART
            raise RuntimeError("stream failed")

        # The real cause must survive a failing cleanup.
        with pytest.raises(RuntimeError, match="stream failed"):
            await _store(_AbortFails()).put("k", _boom())

    async def test_bytes_body_defers_to_core_single_put(self) -> None:
        # Nothing to stream, so it should take core's put_object path, not multipart.
        client = _FakeS3Client()
        await _store(client).put("k", b"hello")
        assert client.single_put == b"hello"
        assert client.parts == []


class TestInheritedFromCore:
    async def test_get_streams_body_in_chunks(self) -> None:
        client = _FakeS3Client(objects={"k": b"hello world"})
        store = StreamingS3Store(S3Config(bucket="b", chunk_size=5), client=client)
        chunks = [chunk async for chunk in await store.get("k")]
        assert b"".join(chunks) == b"hello world"

    async def test_list_follows_pagination(self) -> None:
        pages = [
            {
                "Contents": [{"Key": "a"}, {"Key": "b"}],
                "IsTruncated": True,
                "NextContinuationToken": "1",
            },
            {"Contents": [{"Key": "c"}], "IsTruncated": False},
        ]
        store = _store(_FakeS3Client(pages=pages))
        assert [key async for key in await store.list("")] == ["a", "b", "c"]

    async def test_delete_is_available(self) -> None:
        client = _FakeS3Client(objects={"k": b"x"})
        await _store(client).delete("k")
        assert "k" not in client._objects


class TestKeyValidationRestored:
    """The regression PIR-690 exists to fix: the old S3BlobStore validated nothing."""

    @pytest.mark.parametrize(
        "key",
        ["", "/leading-slash", "../escape", "nested/../../escape", "with\x00nul"],
    )
    async def test_put_rejects_unsafe_key(self, key: str) -> None:
        client = _FakeS3Client()
        with pytest.raises(ValueError):
            await _store(client).put(key, _stream(b"x"))
        # Rejected before any upload was started.
        assert client.parts == []
        assert client.aborted is False

    @pytest.mark.parametrize("key", ["", "/leading-slash", "../escape", "with\x00nul"])
    async def test_bytes_put_rejects_unsafe_key(self, key: str) -> None:
        client = _FakeS3Client()
        with pytest.raises(ValueError):
            await _store(client).put(key, b"x")
        assert client.single_put is None

    @pytest.mark.parametrize("key", ["", "/leading-slash", "../escape", "with\x00nul"])
    async def test_get_rejects_unsafe_key(self, key: str) -> None:
        with pytest.raises(ValueError):
            await _store(_FakeS3Client()).get(key)

    @pytest.mark.parametrize("key", ["", "/leading-slash", "../escape", "with\x00nul"])
    async def test_delete_rejects_unsafe_key(self, key: str) -> None:
        client = _FakeS3Client(objects={"k": b"x"})
        with pytest.raises(ValueError):
            await _store(client).delete(key)
        assert client._objects == {"k": b"x"}


class TestConfig:
    def test_is_a_core_object_store(self) -> None:
        assert isinstance(_store(_FakeS3Client()), ObjectStore)

    def test_rejects_empty_bucket(self) -> None:
        with pytest.raises(ValueError, match="bucket"):
            StreamingS3Store(S3Config(bucket=""))

    def test_rejects_part_size_below_s3_minimum(self) -> None:
        for value in (0, 1024, 5 * 1024 * 1024 - 1):
            with pytest.raises(ValueError, match="at least"):
                StreamingS3Store(S3Config(bucket="b"), part_size=value)

    def test_part_size_defaults_to_config_multipart_threshold(self) -> None:
        config = S3Config(bucket="b", multipart_threshold=16 * 1024 * 1024)
        assert StreamingS3Store(config, client=_FakeS3Client()).part_size == 16 * 1024 * 1024

    def test_exposes_part_size(self) -> None:
        assert _store(_FakeS3Client(), part_size=_PART * 2).part_size == _PART * 2
