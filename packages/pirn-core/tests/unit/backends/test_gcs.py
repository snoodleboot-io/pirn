"""Tests for GCSDataStore (SDK stubbed).

The store composes over :class:`pirn.connectors.object_storage.gcs_store.GCSStore`
(PIR-869); the stub below is the same gcloud-aio-storage slice that
``tests/unit/domains/connectors/object_storage/test_gcs_store.py`` uses, plus
``download_metadata`` for ``has()``.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.gcs_data_store import GCSDataStore


class _DownloadStream:
    def __init__(self, data: bytes) -> None:
        self._buf = data

    async def read(self, n: int) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk

    async def close(self) -> None:
        return None


class _StubStorage:
    """The slice of ``gcloud.aio.storage.Storage`` the data store reaches."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.closed = 0

    async def download_stream(self, *, bucket: str, object_name: str) -> _DownloadStream:
        if (bucket, object_name) not in self.objects:
            raise Exception("404 Not Found")
        return _DownloadStream(self.objects[(bucket, object_name)])

    async def upload(self, *, bucket: str, object_name: str, file_data: bytes) -> dict[str, Any]:
        self.objects[(bucket, object_name)] = file_data
        return {"name": object_name}

    async def download_metadata(self, bucket: str, object_name: str) -> dict[str, Any]:
        if (bucket, object_name) not in self.objects:
            raise Exception("404 Not Found")
        return {}

    async def delete(self, *, bucket: str, object_name: str) -> None:
        self.objects.pop((bucket, object_name), None)

    async def close(self) -> None:
        self.closed += 1


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
        self.storage = _StubStorage()
        self.store = GCSDataStore(bucket="test-bucket", client=self.storage, allow_unsigned=True)

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

    async def test_objects_land_in_bucket_under_prefix(self) -> None:
        await self.store.put("sha256:abc", 1)
        self.assertIn(("test-bucket", "pirn/data/abc"), self.storage.objects)

    async def test_injected_client_is_not_closed_by_the_store(self) -> None:
        """A caller-owned client outlives the data store; only owned clients are closed."""
        await self.store.put("sha256:abc", 1)
        await self.store.close()
        self.assertEqual(self.storage.closed, 0)
