"""Tests for LocalDiskDataStore (beyond signing tests in test_data_store_signing.py)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.backends.disk import LocalDiskDataStore


class TestLocalDiskDataStoreKeyLayout(unittest.TestCase):
    """Object key derivation uses two-char prefix sharding."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.store = LocalDiskDataStore(self.root, allow_unsigned=True)

    def test_object_key_strips_sha256_prefix(self) -> None:
        key = self.store._object_key("sha256:abcdef1234")
        self.assertNotIn("sha256:", key)

    def test_object_key_uses_two_char_prefix_dir(self) -> None:
        key = self.store._object_key("sha256:abcdef1234")
        path = Path(key)
        # Parent dir name should be first 2 chars of clean hash
        self.assertEqual(path.parent.name, "ab")

    def test_object_key_short_hash_uses_underscore(self) -> None:
        key = self.store._object_key("x")
        path = Path(key)
        self.assertEqual(path.parent.name, "_")

    def test_object_key_without_prefix(self) -> None:
        key = self.store._object_key("abcdef12")
        self.assertIn("ab", key)

    def test_root_created_on_init(self) -> None:
        new_root = self.root / "nested" / "dir"
        _ = LocalDiskDataStore(new_root, allow_unsigned=True)
        self.assertTrue(new_root.exists())


class TestLocalDiskDataStoreCRUD(unittest.IsolatedAsyncioTestCase):
    """put / get / has / scrub on real filesystem."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.store = LocalDiskDataStore(Path(self.td.name), allow_unsigned=True)

    async def test_put_then_get_round_trip(self) -> None:
        await self.store.put("sha256:abc123", [1, 2, 3])
        result = await self.store.get("sha256:abc123")
        self.assertEqual(result, [1, 2, 3])

    async def test_has_false_before_put(self) -> None:
        self.assertFalse(await self.store.has("sha256:nothere"))

    async def test_has_true_after_put(self) -> None:
        await self.store.put("sha256:x", 99)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_scrub_removes_file(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_scrub_missing_is_idempotent(self) -> None:
        await self.store.scrub("sha256:nonexistent")

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_file_written_to_disk(self) -> None:
        await self.store.put("sha256:abcdef", 42)
        key_path = Path(self.store._object_key("sha256:abcdef"))
        self.assertTrue(key_path.exists())

    async def test_put_creates_parent_directory(self) -> None:
        await self.store.put("sha256:abcdef", "val")
        key_path = Path(self.store._object_key("sha256:abcdef"))
        self.assertTrue(key_path.parent.exists())

    async def test_stores_complex_object(self) -> None:
        obj = {"nested": {"a": 1}, "list": [True, None, 3.14]}
        await self.store.put("sha256:complex", obj)
        result = await self.store.get("sha256:complex")
        self.assertEqual(result, obj)
