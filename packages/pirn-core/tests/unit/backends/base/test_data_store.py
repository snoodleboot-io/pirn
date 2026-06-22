"""Tests for DataStore interface contract."""

from __future__ import annotations

import unittest

from pirn.backends.base.data_store import DataStore


class TestDataStoreInterface(unittest.IsolatedAsyncioTestCase):
    """DataStore is an abstract interface; all methods raise NotImplementedError."""

    def _make_store(self) -> DataStore:
        return DataStore()

    async def test_put_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            await store.put("sha256:abc", 42)
        self.assertIn("put()", str(ctx.exception))

    async def test_get_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            await store.get("sha256:abc")
        self.assertIn("get()", str(ctx.exception))

    async def test_has_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            await store.has("sha256:abc")
        self.assertIn("has()", str(ctx.exception))

    async def test_scrub_raises_not_implemented(self) -> None:
        store = self._make_store()
        with self.assertRaises(NotImplementedError) as ctx:
            await store.scrub("sha256:abc")
        self.assertIn("scrub()", str(ctx.exception))

    def test_error_message_includes_class_name(self) -> None:
        class MyStore(DataStore):
            pass

        store = MyStore()

        async def _run() -> None:
            await store.put("x", 1)

        import asyncio

        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(_run())
        self.assertIn("MyStore", str(ctx.exception))
