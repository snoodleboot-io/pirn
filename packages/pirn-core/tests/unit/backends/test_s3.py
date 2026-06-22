"""Tests for S3DataStore (cloud SDK mocked)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends._signer import _Signer
from pirn.backends.s3 import S3DataStore


def _make_s3_mock(stored: dict[str, bytes]) -> tuple[Any, Any]:
    mock_s3 = AsyncMock()

    async def fake_put_object(**kwargs: Any) -> None:
        stored[kwargs["Key"]] = kwargs["Body"]

    class _NoSuchKey(Exception):
        pass
    _NoSuchKey.__name__ = "NoSuchKey"

    async def fake_get_object(**kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]
        if key not in stored:
            raise _NoSuchKey("NoSuchKey: key not found")
        body_mock = AsyncMock()
        body_mock.read = AsyncMock(return_value=stored[key])
        return {"Body": body_mock}

    async def fake_head_object(**kwargs: Any) -> None:
        if kwargs["Key"] not in stored:
            raise Exception("NoSuchKey")

    async def fake_delete_object(**kwargs: Any) -> None:
        stored.pop(kwargs["Key"], None)

    mock_s3.put_object = fake_put_object
    mock_s3.get_object = fake_get_object
    mock_s3.head_object = fake_head_object
    mock_s3.delete_object = fake_delete_object

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_s3)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=ctx)
    return mock_session, stored


class TestS3DataStoreConstruction(unittest.TestCase):
    def test_refuses_unsigned_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            S3DataStore(bucket="my-bucket")

    def test_allow_unsigned_permits_construction(self) -> None:
        store = S3DataStore(bucket="my-bucket", allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_accepts_signer(self) -> None:
        store = S3DataStore(bucket="my-bucket", signer=_Signer.test_signer())
        self.assertIsNotNone(store)


class TestS3DataStoreObjectKey(unittest.TestCase):
    def test_key_strips_sha256_prefix(self) -> None:
        store = S3DataStore(bucket="b", allow_unsigned=True)
        key = store._object_key("sha256:abcdef")
        self.assertNotIn("sha256:", key)
        self.assertIn("abcdef", key)

    def test_key_uses_configured_prefix(self) -> None:
        store = S3DataStore(bucket="b", prefix="custom/prefix/", allow_unsigned=True)
        key = store._object_key("sha256:abc")
        self.assertTrue(key.startswith("custom/prefix/"))


class TestS3DataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stored: dict[str, bytes] = {}
        self.session, _ = _make_s3_mock(self.stored)
        self.store = S3DataStore(
            bucket="test-bucket",
            session=self.session,
            allow_unsigned=True,
        )

    async def test_put_then_get_round_trip(self) -> None:
        await self.store.put("sha256:abc", {"x": 1})
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, {"x": 1})

    async def test_has_returns_false_for_missing(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 42)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_object(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")


class TestS3DataStoreEndpointConfig(unittest.TestCase):
    def test_endpoint_url_passed_to_client(self) -> None:
        stored: dict[str, bytes] = {}
        session, _ = _make_s3_mock(stored)
        store = S3DataStore(
            bucket="b",
            endpoint_url="http://minio:9000",
            session=session,
            allow_unsigned=True,
        )
        self.assertEqual(store._endpoint_url, "http://minio:9000")

    def test_region_stored(self) -> None:
        store = S3DataStore(bucket="b", region="us-east-1", allow_unsigned=True)
        self.assertEqual(store._region, "us-east-1")
