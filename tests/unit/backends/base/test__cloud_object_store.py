"""Tests for _CloudObjectStore serialization/signing mixin."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore


def _make_concrete_store(**kwargs: Any) -> "_CloudObjectStore":
    """Build a minimal concrete subclass for testing the mixin."""

    class _ConcreteStore(_CloudObjectStore):
        def __init__(self, storage: dict[str, bytes], **kw: Any) -> None:
            super().__init__(**kw)
            self._storage = storage

        def _object_key(self, content_hash: str) -> str:
            return f"objects/{content_hash}"

        async def _put_bytes(self, key: str, payload: bytes) -> None:
            self._storage[key] = payload

        async def _get_bytes(self, key: str) -> bytes:
            if key not in self._storage:
                raise KeyError(key)
            return self._storage[key]

        async def _has_key(self, key: str) -> bool:
            return key in self._storage

        async def _delete_key(self, key: str) -> None:
            self._storage.pop(key, None)

    storage: dict[str, bytes] = {}
    return _ConcreteStore(storage, **kwargs)


class TestCloudObjectStoreUnsignedGuard(unittest.TestCase):
    """Construction must be refused unless signed or explicitly unsigned."""

    def test_refuses_unsigned_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            _make_concrete_store()

    def test_allow_unsigned_true_permits_construction(self) -> None:
        store = _make_concrete_store(allow_unsigned=True)
        self.assertIsNotNone(store)

    def test_signer_provided_permits_construction(self) -> None:
        signer = _Signer.test_signer()
        store = _make_concrete_store(signer=signer)
        self.assertIsNotNone(store)


class TestCloudObjectStoreOperations(unittest.IsolatedAsyncioTestCase):
    """put/get/has/scrub route through the serialization layer."""

    def _make_unsigned(self) -> "_CloudObjectStore":
        return _make_concrete_store(allow_unsigned=True)

    def _make_signed(self) -> "_CloudObjectStore":
        return _make_concrete_store(signer=_Signer.test_signer())

    async def test_unsigned_round_trip(self) -> None:
        store = self._make_unsigned()
        await store.put("sha256:abc", {"x": 1})
        result = await store.get("sha256:abc")
        self.assertEqual(result, {"x": 1})

    async def test_signed_round_trip(self) -> None:
        store = self._make_signed()
        await store.put("sha256:abc", [1, 2, 3])
        result = await store.get("sha256:abc")
        self.assertEqual(result, [1, 2, 3])

    async def test_has_returns_true_after_put(self) -> None:
        store = self._make_unsigned()
        await store.put("sha256:x", 99)
        self.assertTrue(await store.has("sha256:x"))

    async def test_has_returns_false_for_missing(self) -> None:
        store = self._make_unsigned()
        self.assertFalse(await store.has("sha256:missing"))

    async def test_scrub_removes_value(self) -> None:
        store = self._make_unsigned()
        await store.put("sha256:x", "hello")
        await store.scrub("sha256:x")
        self.assertFalse(await store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        store = self._make_unsigned()
        with self.assertRaises(KeyError):
            await store.get("sha256:missing")

    async def test_object_key_delegates_to_subclass(self) -> None:
        store = self._make_unsigned()
        key = store._object_key("sha256:aabbcc")
        self.assertIn("sha256:aabbcc", key)

    async def test_signed_get_with_tampered_payload_raises(self) -> None:
        store = self._make_signed()
        await store.put("sha256:abc", "data")
        # Tamper with the raw bytes in the underlying storage
        raw_key = store._object_key("sha256:abc")
        store._storage[raw_key] = b"\x00" * 64  # garbage
        with self.assertRaises((ValueError, Exception)):
            await store.get("sha256:abc")

    async def test_abstract_put_bytes_raises(self) -> None:
        store = _CloudObjectStore.__new__(_CloudObjectStore)
        with self.assertRaises(NotImplementedError):
            await store._put_bytes("k", b"")

    async def test_abstract_get_bytes_raises(self) -> None:
        store = _CloudObjectStore.__new__(_CloudObjectStore)
        with self.assertRaises(NotImplementedError):
            await store._get_bytes("k")

    async def test_abstract_has_key_raises(self) -> None:
        store = _CloudObjectStore.__new__(_CloudObjectStore)
        with self.assertRaises(NotImplementedError):
            await store._has_key("k")

    async def test_abstract_delete_key_raises(self) -> None:
        store = _CloudObjectStore.__new__(_CloudObjectStore)
        with self.assertRaises(NotImplementedError):
            await store._delete_key("k")

    def test_abstract_object_key_raises(self) -> None:
        store = _CloudObjectStore.__new__(_CloudObjectStore)
        with self.assertRaises(NotImplementedError):
            store._object_key("x")
