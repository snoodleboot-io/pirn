"""Tests for LakehouseTable interface contract."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn_data.lakehouse.lakehouse_table import LakehouseTable


class TestLakehouseTableInterface(unittest.IsolatedAsyncioTestCase):
    """All abstract methods raise NotImplementedError with class name."""

    def _make_table(self) -> LakehouseTable:
        return LakehouseTable()

    def test_name_raises_not_implemented(self) -> None:
        table = self._make_table()
        with self.assertRaises(NotImplementedError) as ctx:
            _ = table.name
        self.assertIn("name", str(ctx.exception))

    async def test_scan_raises_not_implemented(self) -> None:
        table = self._make_table()
        with self.assertRaises(NotImplementedError) as ctx:
            await table.scan()
        self.assertIn("scan()", str(ctx.exception))

    async def test_append_raises_not_implemented(self) -> None:
        table = self._make_table()

        async def _empty() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield

        with self.assertRaises(NotImplementedError) as ctx:
            await table.append(_empty())
        self.assertIn("append()", str(ctx.exception))

    async def test_overwrite_raises_not_implemented(self) -> None:
        table = self._make_table()

        async def _empty() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield

        with self.assertRaises(NotImplementedError) as ctx:
            await table.overwrite(_empty())
        self.assertIn("overwrite()", str(ctx.exception))

    async def test_merge_raises_not_implemented(self) -> None:
        table = self._make_table()

        async def _empty() -> AsyncIterator[Mapping[str, Any]]:
            return
            yield

        with self.assertRaises(NotImplementedError) as ctx:
            await table.merge(_empty(), on=["id"])
        self.assertIn("merge()", str(ctx.exception))

    async def test_history_raises_not_implemented(self) -> None:
        table = self._make_table()
        with self.assertRaises(NotImplementedError) as ctx:
            await table.history()
        self.assertIn("history()", str(ctx.exception))

    async def test_close_raises_not_implemented(self) -> None:
        table = self._make_table()
        with self.assertRaises(NotImplementedError) as ctx:
            await table.close()
        self.assertIn("close()", str(ctx.exception))

    def test_error_message_includes_subclass_name(self) -> None:
        class MyTable(LakehouseTable):
            pass

        table = MyTable()
        with self.assertRaises(NotImplementedError) as ctx:
            _ = table.name
        self.assertIn("MyTable", str(ctx.exception))


class TestLakehouseTableClearCredentials(unittest.TestCase):
    def test_clear_credentials_nils_config(self) -> None:
        table = LakehouseTable()
        table._config = {"secret": "value"}
        table._clear_credentials()
        self.assertIsNone(table._config)

    def test_clear_credentials_no_config_attribute_is_safe(self) -> None:
        table = LakehouseTable()
        # _config not set — must not raise
        table._clear_credentials()
