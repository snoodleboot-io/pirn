"""Tests for :class:`ScdType3PreviousValue`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.scd.scd_type_3_previous_value import (
    ScdType3PreviousValue,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):

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
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd3.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  name_previous TEXT,"
            "  region_previous TEXT"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        await self.target_pool.close()
        self._tmp_target_pool.cleanup()

    def _make_knot(self, **kwargs: Any) -> ScdType3PreviousValue:
        defaults: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, name, region FROM customers",
            "target_pool": self.target_pool,
            "target_table": "customers",
            "key_columns": ("id",),
            "tracked_columns": ("name", "region"),
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType3PreviousValue(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ScdType3PreviousValue, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, name, region FROM customers",
            "target_pool": self.target_pool,
            "target_table": "customers",
            "key_columns": ("id",),
            "tracked_columns": ("name", "region"),
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")

    async def test_rejects_overlapping_key_and_tracked(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id", "name"), tracked_columns=("name", "region"))

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad table")


class TestScdType3Behaviour(unittest.IsolatedAsyncioTestCase):

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
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd3.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  name_previous TEXT,"
            "  region_previous TEXT"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
        self._tmp_target_pool.cleanup()
    async def test_first_run_inserts_with_null_previous(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region, name_previous, region_previous "
            "FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[3] is None
            assert row[4] is None

    async def test_second_run_shifts_current_to_previous(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, region, region_previous FROM customers ORDER BY id"
        )
        alice = next(r for r in rows if r[0] == 1)
        assert alice[1] == "APAC"
        assert alice[2] == "EU"
        bob = next(r for r in rows if r[0] == 2)
        assert bob[1] == "US"
        assert bob[2] is None

    async def test_unchanged_row_not_modified(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT name_previous FROM customers ORDER BY id"
        )
        for row in rows:
            assert row[0] is None
