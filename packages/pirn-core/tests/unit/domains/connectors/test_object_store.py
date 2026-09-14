"""Tests for :class:`ObjectStore`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from pirn.connectors.object_store import ObjectStore


class TestObjectStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_get_raises_not_implemented(self) -> None:
        store = ObjectStore()
        with self.assertRaises(NotImplementedError):
            await store.get("key")

    async def test_put_raises_not_implemented(self) -> None:
        store = ObjectStore()
        with self.assertRaises(NotImplementedError):
            await store.put("key", b"data")

    async def test_delete_raises_not_implemented(self) -> None:
        store = ObjectStore()
        with self.assertRaises(NotImplementedError):
            await store.delete("key")

    async def test_list_raises_not_implemented(self) -> None:
        store = ObjectStore()
        with self.assertRaises(NotImplementedError):
            await store.list()

    async def test_close_default_holds_nothing_and_is_repeatable(self) -> None:
        # Arrange
        store = ObjectStore()
        # Act
        await store.close()
        await store.close()
        # Assert — a store with no SDK session closes without error.
        self.assertIsInstance(store, ObjectStore)


class TestObjectStoreValidateKey(unittest.TestCase):
    def setUp(self) -> None:
        self._store = ObjectStore()

    def test_empty_key_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._store._validate_key("")

    def test_nul_byte_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._store._validate_key("a\x00b")

    def test_leading_slash_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._store._validate_key("/absolute/path")

    def test_dotdot_segment_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._store._validate_key("foo/../bar")

    def test_valid_key_passes(self) -> None:
        self._store._validate_key("bucket/prefix/file.json")


class _ListOnlyStore(ObjectStore):
    """Implements only ``list`` so the base ``exists`` default is what runs."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = keys

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        return self._names([k for k in self._keys if k.startswith(prefix)])

    @staticmethod
    async def _names(names: list[str]) -> AsyncIterator[str]:
        for name in names:
            yield name


class TestObjectStoreExistsDefault(unittest.IsolatedAsyncioTestCase):
    """``exists`` falls back to an exact match over ``list(prefix=key)`` (PIR-869)."""

    async def test_true_for_exact_key(self) -> None:
        self.assertTrue(await _ListOnlyStore(["a/b", "a/bc"]).exists("a/b"))

    async def test_false_when_only_a_longer_key_shares_the_prefix(self) -> None:
        self.assertFalse(await _ListOnlyStore(["a/bc"]).exists("a/b"))

    async def test_false_for_missing_key(self) -> None:
        self.assertFalse(await _ListOnlyStore([]).exists("a/b"))

    async def test_validates_key(self) -> None:
        with self.assertRaises(ValueError):
            await _ListOnlyStore([]).exists("")

    async def test_default_raises_not_implemented_without_list(self) -> None:
        with self.assertRaises(NotImplementedError):
            await ObjectStore().exists("key")

    def test_is_not_found_default_recognises_nothing(self) -> None:
        self.assertFalse(ObjectStore().is_not_found(KeyError("k")))
        self.assertFalse(ObjectStore().is_not_found(FileNotFoundError("k")))
