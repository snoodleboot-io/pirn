"""Tests for GCSDataStore (SDK mocked)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends._signer import _Signer
from pirn.backends.gcs import GCSDataStore


def _make_gcs_storage_mock(stored: dict[str, bytes]) -> MagicMock:
    """Return a mock gcloud.aio.storage.Storage."""
    storage = MagicMock()

    async def _upload(bucket: str, key: str, data: bytes) -> None:
        stored[key] = data

    async def _download(bucket: str, key: str) -> bytes:
        if key not in stored:
            raise Exception("404 Not Found")
        return stored[key]

    async def _download_metadata(bucket: str, key: str) -> dict:
        if key not in stored:
            raise Exception("404 Not Found")
        return {}

    async def _delete(bucket: str, key: str) -> None:
        stored.pop(key, None)

    storage.upload = _upload
    storage.download = _download
    storage.download_metadata = _download_metadata
    storage.delete = _delete
    storage.__aenter__ = AsyncMock(return_value=storage)
    storage.__aexit__ = AsyncMock(return_value=False)
    return storage


class TestGCSDataStoreConstruction(unittest.TestCase):
    def test_refuses_unsigned_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            GCSDataStore(bucket="my-bucket")

    def test_allow_unsigned_permits_construction(self) -> None:
        store = GCSDataStore(bucket="my-bucket", allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_accepts_signer(self) -> None:
        store = GCSDataStore(bucket="my-bucket", signer=_Signer.test_signer())
        self.assertIsNotNone(store)


class TestGCSDataStoreObjectKey(unittest.TestCase):
    def test_key_strips_sha256_prefix(self) -> None:
        store = GCSDataStore(bucket="b", allow_unsigned=True)
        key = store._object_key("sha256:abcdef")
        self.assertNotIn("sha256:", key)
        self.assertIn("abcdef", key)

    def test_key_uses_prefix(self) -> None:
        store = GCSDataStore(bucket="b", prefix="gcs/data/", allow_unsigned=True)
        key = store._object_key("sha256:abc")
        self.assertTrue(key.startswith("gcs/data/"))


class TestGCSDataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stored: dict[str, bytes] = {}
        self.mock_storage = _make_gcs_storage_mock(self.stored)

        # Patch __storage to return our mock
        self.store = GCSDataStore(bucket="test-bucket", allow_unsigned=True)
        self.store._GCSDataStore__storage = MagicMock(return_value=self.mock_storage)

    async def test_put_then_get_round_trip(self) -> None:
        await self.store.put("sha256:abc", [1, 2, 3])
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, [1, 2, 3])

    async def test_has_returns_false_for_missing(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 99)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_object(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")
