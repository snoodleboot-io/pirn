"""Tests for _CloudObjectStore serialization/signing mixin."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore
from pirn.connectors.object_store import ObjectStore


def _make_concrete_store(**kwargs: Any) -> _CloudObjectStore:
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

    def _make_unsigned(self) -> _CloudObjectStore:
        return _make_concrete_store(allow_unsigned=True)

    def _make_signed(self) -> _CloudObjectStore:
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
        store = _CloudObjectStore(allow_unsigned=True)
        with self.assertRaises(NotImplementedError):
            await store._put_bytes("k", b"")

    async def test_abstract_get_bytes_raises(self) -> None:
        store = _CloudObjectStore(allow_unsigned=True)
        with self.assertRaises(NotImplementedError):
            await store._get_bytes("k")

    async def test_abstract_has_key_raises(self) -> None:
        store = _CloudObjectStore(allow_unsigned=True)
        with self.assertRaises(NotImplementedError):
            await store._has_key("k")

    async def test_abstract_delete_key_raises(self) -> None:
        store = _CloudObjectStore(allow_unsigned=True)
        with self.assertRaises(NotImplementedError):
            await store._delete_key("k")

    def test_abstract_build_object_store_raises(self) -> None:
        store = _CloudObjectStore(allow_unsigned=True)
        with self.assertRaises(NotImplementedError):
            store._build_object_store()

    def test_default_object_key_strips_prefix_and_applies_configured_prefix(self) -> None:
        store = _CloudObjectStore(allow_unsigned=True, prefix="p/")
        self.assertEqual(store._object_key("sha256:abc"), "p/abc")


# --- composition over an ObjectStore (PIR-869) ------------------------------


class _Missing(Exception):
    """The fake backend's own not-found error, as an SDK would raise it."""


class _FakeObjectStore(ObjectStore):
    """In-memory ``ObjectStore`` that counts how often it is closed."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.closed = 0

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)
        if key not in self.objects:
            raise _Missing(key)
        return self._chunks(self.objects[key])

    @staticmethod
    async def _chunks(data: bytes) -> AsyncIterator[bytes]:
        for start in range(0, len(data), 4):
            yield data[start : start + 4]

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        self._validate_key(key)
        assert isinstance(body, bytes)
        self.objects[key] = body

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        return self._names(sorted(k for k in self.objects if k.startswith(prefix)))

    @staticmethod
    async def _names(names: list[str]) -> AsyncIterator[str]:
        for name in names:
            yield name

    def is_not_found(self, exc: BaseException) -> bool:
        return isinstance(exc, _Missing)

    async def close(self) -> None:
        self.closed += 1


class _ComposedStore(_CloudObjectStore):
    """A data store that composes over ``_FakeObjectStore`` and counts builds."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(prefix="objects/", **kw)
        self.builds: list[_FakeObjectStore] = []

    def _build_object_store(self) -> ObjectStore:
        store = _FakeObjectStore()
        self.builds.append(store)
        return store


class TestCloudObjectStoreComposition(unittest.IsolatedAsyncioTestCase):
    """put/get/has/scrub delegate to the composed ObjectStore."""

    def setUp(self) -> None:
        self.store = _ComposedStore(allow_unsigned=True)

    async def test_round_trip_through_object_store(self) -> None:
        await self.store.put("sha256:abc", {"x": 1})
        self.assertEqual(await self.store.get("sha256:abc"), {"x": 1})
        self.assertIn("objects/abc", self.store.builds[0].objects)

    async def test_backend_not_found_becomes_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_other_backend_errors_propagate(self) -> None:
        class _Boom(Exception):
            pass

        async def _get(key: str) -> AsyncIterator[bytes]:
            raise _Boom(key)

        await self.store.put("sha256:abc", 1)
        self.store.builds[0].get = _get  # type: ignore[method-assign]
        with self.assertRaises(_Boom):
            await self.store.get("sha256:abc")

    async def test_has_uses_exists(self) -> None:
        self.assertFalse(await self.store.has("sha256:x"))
        await self.store.put("sha256:x", 1)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_deletes(self) -> None:
        await self.store.put("sha256:x", 1)
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_signed_round_trip_through_object_store(self) -> None:
        store = _ComposedStore(signer=_Signer.test_signer())
        await store.put("sha256:abc", [1, 2])
        self.assertEqual(await store.get("sha256:abc"), [1, 2])


class TestCloudObjectStoreLifecycle(unittest.IsolatedAsyncioTestCase):
    """One ObjectStore (one client) for N operations; closed exactly once."""

    def setUp(self) -> None:
        self.store = _ComposedStore(allow_unsigned=True)

    async def test_nothing_built_before_first_use(self) -> None:
        self.assertEqual(self.store.builds, [])

    async def test_one_object_store_for_many_operations(self) -> None:
        for i in range(10):
            await self.store.put(f"sha256:{i}", i)
        await self.store.get("sha256:3")
        await self.store.has("sha256:4")
        await self.store.scrub("sha256:5")
        self.assertEqual(len(self.store.builds), 1)

    async def test_close_closes_the_object_store_once(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.close()
        await self.store.close()
        self.assertEqual(self.store.builds[0].closed, 1)

    async def test_close_before_use_builds_nothing(self) -> None:
        await self.store.close()
        self.assertEqual(self.store.builds, [])

    async def test_use_after_close_rebuilds_and_close_releases_again(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.close()
        await self.store.put("sha256:b", 2)
        await self.store.close()
        self.assertEqual(len(self.store.builds), 2)
        self.assertEqual([s.closed for s in self.store.builds], [1, 1])
