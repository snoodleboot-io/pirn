"""Mock-driver tests for the S3 DataStore."""

from __future__ import annotations

import pickle
from contextlib import asynccontextmanager

import pytest

from pirn.backends.s3 import S3DataStore

# ---------------------------------------------------- fake S3 client


class _FakeS3Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


class _NoSuchKey(Exception):
    pass


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> dict:
        self.objects[Key] = Body
        return {"ETag": "fake"}

    async def get_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise _NoSuchKey("NoSuchKey")
        return {"Body": _FakeS3Body(self.objects[Key])}

    async def head_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise _NoSuchKey("NoSuchKey")
        return {"ContentLength": len(self.objects[Key])}

    async def delete_object(self, *, Bucket: str, Key: str) -> dict:
        self.objects.pop(Key, None)
        return {}


class _FakeSession:
    def __init__(self) -> None:
        self.s3 = _FakeS3Client()

    @asynccontextmanager
    async def client(
        self, service: str, region_name: str | None = None, endpoint_url: str | None = None
    ):
        assert service == "s3"
        yield self.s3


# ---------------------------------------------------- tests


async def test_s3_data_store_put_writes_to_correct_key():
    session = _FakeSession()
    ds = S3DataStore(bucket="mybucket", session=session)
    await ds.put("sha256:abc123", {"x": 1})

    assert "pirn/data/abc123" in session.s3.objects
    stored = session.s3.objects["pirn/data/abc123"]
    assert pickle.loads(stored) == {"x": 1}


async def test_s3_data_store_custom_prefix():
    session = _FakeSession()
    ds = S3DataStore(bucket="mybucket", prefix="myproject/", session=session)
    await ds.put("sha256:abc", "v")
    assert "myproject/abc" in session.s3.objects


async def test_s3_data_store_get_round_trips():
    session = _FakeSession()
    ds = S3DataStore(bucket="b", session=session)
    await ds.put("sha256:k", [1, 2, 3])
    assert await ds.get("sha256:k") == [1, 2, 3]


async def test_s3_data_store_get_missing_raises_keyerror():
    session = _FakeSession()
    ds = S3DataStore(bucket="b", session=session)
    with pytest.raises(KeyError):
        await ds.get("sha256:nope")


async def test_s3_data_store_has_reflects_presence():
    session = _FakeSession()
    ds = S3DataStore(bucket="b", session=session)
    assert not await ds.has("sha256:k")
    await ds.put("sha256:k", 1)
    assert await ds.has("sha256:k")


async def test_s3_data_store_scrub_deletes():
    session = _FakeSession()
    ds = S3DataStore(bucket="b", session=session)
    await ds.put("sha256:k", "v")
    await ds.scrub("sha256:k")
    assert not await ds.has("sha256:k")


async def test_s3_data_store_strips_sha256_prefix_from_keys():
    """Keys in S3 should be the hex digest, not the 'sha256:' prefix —
    cleaner to read in S3 console."""
    session = _FakeSession()
    ds = S3DataStore(bucket="b", session=session)
    await ds.put("sha256:deadbeef", "v")
    assert "pirn/data/deadbeef" in session.s3.objects
    assert "pirn/data/sha256:deadbeef" not in session.s3.objects
