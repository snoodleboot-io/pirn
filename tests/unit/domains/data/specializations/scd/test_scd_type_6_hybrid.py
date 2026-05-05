"""Tests for :class:`ScdType6Hybrid`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_6_hybrid import ScdType6Hybrid
from pirn.tapestry import Tapestry


def _make_scd6(source_pool: SqlitePool, target_pool: SqlitePool) -> ScdType6Hybrid:
    return ScdType6Hybrid(
        source_pool=source_pool,
        source_query="SELECT id, name, region FROM customers",
        target_pool=target_pool,
        target_table="customers",
        key_columns=("id",),
        tracked_columns=("name", "region"),
        current_columns={"name": "current_name", "region": "current_region"},
        previous_columns={"name": "prev_name", "region": "prev_region"},
        _config=KnotConfig(id="scd6"),
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
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd6.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  current_name TEXT,"
            "  current_region TEXT,"
            "  prev_name TEXT,"
            "  prev_region TEXT,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        await self.target_pool.close()
        self._tmp_target_pool.cleanup()

    def _make_knot(self, **kwargs: Any) -> ScdType6Hybrid:
        defaults: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, name, region FROM customers",
            "target_pool": self.target_pool,
            "target_table": "customers",
            "key_columns": ("id",),
            "tracked_columns": ("name", "region"),
            "current_columns": {"name": "current_name", "region": "current_region"},
            "previous_columns": {"name": "prev_name", "region": "prev_region"},
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType6Hybrid(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ScdType6Hybrid, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, name, region FROM customers",
            "target_pool": self.target_pool,
            "target_table": "customers",
            "key_columns": ("id",),
            "tracked_columns": ("name", "region"),
            "current_columns": {"name": "current_name", "region": "current_region"},
            "previous_columns": {"name": "prev_name", "region": "prev_region"},
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_missing_current_column_entry(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "current_columns missing"):
            await self._call(k, current_columns={"name": "current_name"})

    async def test_rejects_missing_previous_column_entry(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "previous_columns missing"):
            await self._call(k, previous_columns={"name": "prev_name"})

    async def test_rejects_key_tracked_overlap(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(
                k,
                key_columns=("id", "name"),
                current_columns={"name": "current_name", "region": "current_region"},
                previous_columns={"name": "prev_name", "region": "prev_region"},
            )


class TestScdType6Behaviour(unittest.IsolatedAsyncioTestCase):

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
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd6.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  current_name TEXT,"
            "  current_region TEXT,"
            "  prev_name TEXT,"
            "  prev_region TEXT,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
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
            _make_scd6(source_pool, target_pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, valid_to, is_current, prev_name, prev_region "
            "FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[1] is None
            assert row[2] == 1
            assert row[3] is None
            assert row[4] is None

    async def test_second_run_closes_old_and_inserts_new(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            _make_scd6(source_pool, target_pool)
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            _make_scd6(source_pool, target_pool)
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, region, is_current, prev_region "
            "FROM customers ORDER BY id, valid_from"
        )
        assert len(rows) == 3
        old_alice = next(r for r in rows if r[0] == 1 and r[2] == 0)
        assert old_alice[1] == "EU"
        new_alice = next(r for r in rows if r[0] == 1 and r[2] == 1)
        assert new_alice[1] == "APAC"
        assert new_alice[3] == "EU"

    async def test_current_columns_backfilled_on_all_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            _make_scd6(source_pool, target_pool)
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            _make_scd6(source_pool, target_pool)
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, current_region FROM customers WHERE id = 1"
        )
        for row in rows:
            assert row[1] == "APAC"
