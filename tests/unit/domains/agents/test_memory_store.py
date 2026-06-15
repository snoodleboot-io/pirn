"""Unit tests for :class:`MemoryStore`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_store import MemoryStore


class TestMemoryStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_store_raises_not_implemented(self) -> None:
        store = MemoryStore()
        with self.assertRaises(NotImplementedError):
            await store.store("key", {"v": 1})

    async def test_retrieve_raises_not_implemented(self) -> None:
        store = MemoryStore()
        with self.assertRaises(NotImplementedError):
            await store.retrieve("key")

    async def test_search_raises_not_implemented(self) -> None:
        store = MemoryStore()
        with self.assertRaises(NotImplementedError):
            await store.search("query")

    async def test_forget_raises_not_implemented(self) -> None:
        store = MemoryStore()
        with self.assertRaises(NotImplementedError):
            await store.forget("key")

    async def test_close_raises_not_implemented(self) -> None:
        store = MemoryStore()
        with self.assertRaises(NotImplementedError):
            await store.close()

    def test_clear_credentials_nulls_config(self) -> None:
        store = MemoryStore()
        store._clear_credentials()
        assert store._config is None
