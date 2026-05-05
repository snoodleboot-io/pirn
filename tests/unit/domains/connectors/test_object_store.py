"""Tests for :class:`ObjectStore`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.object_store import ObjectStore


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
