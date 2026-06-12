"""Tests for :class:`TableSource`."""

from __future__ import annotations

import unittest

from pirn.connectors.capabilities.table_source import TableSource


class TestTableSourceInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_page_raises_not_implemented(self) -> None:
        source = TableSource()
        with self.assertRaises(NotImplementedError):
            await source.fetch_page()

    async def test_fetch_page_with_cursor_raises_not_implemented(self) -> None:
        source = TableSource()
        with self.assertRaises(NotImplementedError):
            await source.fetch_page(cursor="tok123", page_size=50)
