"""Tests for AzureBlobDataStore (SDK mocked)."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.backends._signer import _Signer
from pirn.backends.azure import AzureBlobDataStore


def _make_azure_mock(stored: dict[str, bytes]) -> MagicMock:
    """Return a mock BlobServiceClient where each blob delegates to stored dict."""

    def _make_blob_client(container: str, blob: str) -> AsyncMock:
        blob_mock = AsyncMock()

        async def _upload(data: bytes, overwrite: bool = False) -> None:
            stored[blob] = data

        class _BlobNotFound(Exception):
            pass
        _BlobNotFound.__name__ = "BlobNotFound"

        async def _download() -> AsyncMock:
            if blob not in stored:
                raise _BlobNotFound("BlobNotFound: blob does not exist")
            stream = AsyncMock()
            stream.readall = AsyncMock(return_value=stored[blob])
            return stream

        async def _exists() -> bool:
            return blob in stored

        async def _delete(delete_snapshots: str | None = None) -> None:
            stored.pop(blob, None)

        blob_mock.upload_blob = _upload
        blob_mock.download_blob = _download
        blob_mock.exists = _exists
        blob_mock.delete_blob = _delete
        return blob_mock

    svc = MagicMock()
    svc.get_blob_client = _make_blob_client
    svc.__aenter__ = AsyncMock(return_value=svc)
    svc.__aexit__ = AsyncMock(return_value=False)
    return svc


class TestAzureBlobDataStoreConstruction(unittest.TestCase):
    def test_refuses_unsigned_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            AzureBlobDataStore(container="c")

    def test_allow_unsigned_permits_construction(self) -> None:
        store = AzureBlobDataStore(container="c", allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_accepts_signer(self) -> None:
        store = AzureBlobDataStore(container="c", signer=_Signer.test_signer())
        self.assertIsNotNone(store)

    def test_raises_without_connection_string_or_account_url(self) -> None:
        store = AzureBlobDataStore(container="c", allow_unsigned=True)
        with self.assertRaises((ValueError, ImportError)):
            store._AzureBlobDataStore__service_client()


class TestAzureBlobDataStoreObjectKey(unittest.TestCase):
    def test_key_strips_sha256_prefix(self) -> None:
        store = AzureBlobDataStore(container="c", allow_unsigned=True)
        key = store._object_key("sha256:abcdef")
        self.assertNotIn("sha256:", key)
        self.assertIn("abcdef", key)

    def test_key_uses_configured_prefix(self) -> None:
        store = AzureBlobDataStore(container="c", prefix="blobs/", allow_unsigned=True)
        key = store._object_key("sha256:abc")
        self.assertTrue(key.startswith("blobs/"))


class TestAzureBlobDataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stored: dict[str, bytes] = {}
        self.mock_svc = _make_azure_mock(self.stored)
        self.store = AzureBlobDataStore(
            container="test-container",
            client=self.mock_svc,
            allow_unsigned=True,
        )

    async def test_put_then_get_round_trip(self) -> None:
        await self.store.put("sha256:abc", {"a": 1})
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, {"a": 1})

    async def test_has_returns_false_for_missing(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 99)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_blob(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")
