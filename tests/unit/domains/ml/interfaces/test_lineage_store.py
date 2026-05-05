"""Tests for :class:`LineageStore`."""

from __future__ import annotations
import unittest


from pirn.domains.ml.lineage_store import LineageStore


class TestLineageStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_log_event_raises_not_implemented(self) -> None:
        store = LineageStore()
        with self.assertRaisesRegex(NotImplementedError, "log_event"):
            await store.log_event("type", {"k": "v"})

    async def test_fetch_lineage_raises_not_implemented(self) -> None:
        store = LineageStore()
        with self.assertRaisesRegex(NotImplementedError, "fetch_lineage"):
            await store.fetch_lineage("model")

    async def test_close_raises_not_implemented(self) -> None:
        store = LineageStore()
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await store.close()
