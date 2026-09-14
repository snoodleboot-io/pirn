"""Tests for S3DataStore (cloud SDK mocked).

The store composes over :class:`pirn.connectors.object_storage.s3_store.S3Store`
(PIR-869): the injected ``session`` is asked for one client on first use and
that client is released by ``close()``.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends.s3_data_store import S3DataStore
from pirn.backends.signer import Signer


def _make_s3_mock(stored: dict[str, bytes]) -> tuple[Any, Any]:
    """A session whose ``client()`` returns an async-context-managed S3 client mock."""
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
        remaining = [stored[key]]

        async def _read(n: int) -> bytes:
            chunk, remaining[0] = remaining[0][:n], remaining[0][n:]
            return chunk

        body_mock.read = _read
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
    mock_session.ctx = ctx
    return mock_session, stored


class TestS3DataStoreConstruction(unittest.TestCase):
    def test_refuses_unsigned_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            S3DataStore(bucket="my-bucket")

    def test_allow_unsigned_permits_construction(self) -> None:
        store = S3DataStore(bucket="my-bucket", allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_accepts_signer(self) -> None:
        store = S3DataStore(bucket="my-bucket", signer=Signer.test_signer())
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

    async def test_objects_land_under_prefix_in_bucket(self) -> None:
        await self.store.put("sha256:deadbeef", "v")
        self.assertIn("pirn/data/deadbeef", self.stored)


class TestS3DataStoreClientLifecycle(unittest.IsolatedAsyncioTestCase):
    """One client for N operations; released exactly once by ``close()`` (PIR-869)."""

    def setUp(self) -> None:
        self.stored: dict[str, bytes] = {}
        self.session, _ = _make_s3_mock(self.stored)
        self.store = S3DataStore(bucket="b", session=self.session, allow_unsigned=True)

    async def test_no_client_until_first_operation(self) -> None:
        self.assertEqual(self.session.client.call_count, 0)

    async def test_one_client_for_many_operations(self) -> None:
        for i in range(5):
            await self.store.put(f"sha256:{i}", i)
        await self.store.get("sha256:0")
        await self.store.has("sha256:1")
        await self.store.scrub("sha256:2")
        self.assertEqual(self.session.client.call_count, 1)
        self.assertEqual(self.session.ctx.__aenter__.await_count, 1)

    async def test_close_releases_the_client_once(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.close()
        await self.store.close()
        self.assertEqual(self.session.ctx.__aexit__.await_count, 1)

    async def test_close_without_use_is_a_no_op(self) -> None:
        await self.store.close()
        self.assertEqual(self.session.client.call_count, 0)
        self.assertEqual(self.session.ctx.__aexit__.await_count, 0)

    async def test_operation_after_close_reopens_a_client(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.close()
        self.assertEqual(await self.store.get("sha256:a"), 1)
        self.assertEqual(self.session.client.call_count, 2)

    async def test_client_built_with_region_and_endpoint(self) -> None:
        store = S3DataStore(
            bucket="b",
            region="eu-west-1",
            endpoint_url="http://minio:9000",
            session=self.session,
            allow_unsigned=True,
        )
        await store.put("sha256:a", 1)
        self.session.client.assert_called_once_with(
            "s3", region_name="eu-west-1", endpoint_url="http://minio:9000"
        )

    async def test_region_none_is_passed_through_as_environment_default(self) -> None:
        await self.store.put("sha256:a", 1)
        self.session.client.assert_called_once_with("s3", region_name=None, endpoint_url=None)


class TestS3DataStoreEndpointConfig(unittest.TestCase):
    def test_endpoint_url_stored(self) -> None:
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
