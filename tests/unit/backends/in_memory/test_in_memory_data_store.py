"""Tests for InMemoryDataStore."""

from __future__ import annotations

import unittest

from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore


class TestInMemoryDataStore(unittest.IsolatedAsyncioTestCase):
    """InMemoryDataStore: put/get/has/scrub semantics."""

    def setUp(self) -> None:
        self.store = InMemoryDataStore()

    async def test_put_then_get_returns_value(self) -> None:
        await self.store.put("sha256:abc", {"key": "value"})
        result = await self.store.get("sha256:abc")
        self.assertEqual(result, {"key": "value"})

    async def test_has_returns_false_before_put(self) -> None:
        self.assertFalse(await self.store.has("sha256:missing"))

    async def test_has_returns_true_after_put(self) -> None:
        await self.store.put("sha256:x", 42)
        self.assertTrue(await self.store.has("sha256:x"))

    async def test_get_missing_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            await self.store.get("sha256:missing")

    async def test_get_key_error_message_contains_hash(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            await self.store.get("sha256:deadbeef")
        self.assertIn("sha256:deadbeef", str(ctx.exception))

    async def test_scrub_removes_value(self) -> None:
        await self.store.put("sha256:x", "hello")
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))

    async def test_scrub_missing_key_is_idempotent(self) -> None:
        # Must not raise even if key doesn't exist
        await self.store.scrub("sha256:nonexistent")

    async def test_put_overwrites_existing_value(self) -> None:
        await self.store.put("sha256:x", "first")
        await self.store.put("sha256:x", "second")
        result = await self.store.get("sha256:x")
        self.assertEqual(result, "second")

    async def test_multiple_independent_hashes(self) -> None:
        await self.store.put("sha256:a", 1)
        await self.store.put("sha256:b", 2)
        self.assertEqual(await self.store.get("sha256:a"), 1)
        self.assertEqual(await self.store.get("sha256:b"), 2)

    async def test_stores_arbitrary_python_objects(self) -> None:
        obj = [1, 2, {"nested": True}]
        await self.store.put("sha256:x", obj)
        self.assertEqual(await self.store.get("sha256:x"), obj)

    async def test_has_false_after_scrub(self) -> None:
        await self.store.put("sha256:x", 99)
        await self.store.scrub("sha256:x")
        self.assertFalse(await self.store.has("sha256:x"))
