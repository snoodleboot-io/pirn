"""Tests for :class:`ScdType1`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.scd.scd_type_1 import ScdType1


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


class TestScdType1Behaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name, region) VALUES (?, ?, ?)",
            [(1, "Alice", "EU"), (2, "Bob", "US")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        await self.target_pool.close()

    async def test_first_run_inserts_all_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region FROM customers ORDER BY id"
        )
        assert rows == [(1, "Alice", "EU"), (2, "Bob", "US")]

    async def test_second_run_overwrites_changed_row(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            ScdType1(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd1"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region FROM customers ORDER BY id"
        )
        assert rows == [(1, "Alice", "APAC"), (2, "Bob", "US")]


class TestValidation(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self, **kwargs: Any) -> ScdType1:
        src = _make_pool()
        tgt = _make_pool()
        defaults: dict[str, Any] = {
            "source_pool": src,
            "source_query": "SELECT 1",
            "target_pool": tgt,
            "target_table": "customers",
            "primary_keys": ("id",),
            "column_names": ("id", "name"),
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType1(**defaults, _config=KnotConfig(id="scd1"))

    async def _call(self, k: ScdType1, **overrides: Any) -> Any:
        src = _make_pool()
        tgt = _make_pool()
        args: dict[str, Any] = {
            "source_pool": src,
            "source_query": "SELECT 1",
            "target_pool": tgt,
            "target_table": "customers",
            "primary_keys": ("id",),
            "column_names": ("id", "name"),
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaises(TypeError):
            await self._call(k, source_pool="not-a-pool")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaises(TypeError):
            await self._call(k, target_pool="not-a-pool")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, source_query="")

    async def test_rejects_pk_outside_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, primary_keys=("missing",))

    async def test_rejects_invalid_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, target_table="customers; DROP TABLE x")
