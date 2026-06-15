"""Tests for :class:`ScdType2`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.scd.scd_type_2 import ScdType2


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    pool.execute_many = AsyncMock(return_value=None)
    return pool


class TestScdType2Behaviour(unittest.IsolatedAsyncioTestCase):

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
        self._tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd2.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        await self.target_pool.close()
        self._tmp.cleanup()

    async def test_first_run_inserts_with_effective_dates(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType2(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd2"),
            )
        assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region, valid_to, is_current "
            "FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[3] is None
            assert row[4] == 1

    async def test_second_run_expires_changed_row(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            ScdType2(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd2"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            ScdType2(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd2"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, region, valid_to, is_current "
            "FROM customers ORDER BY id, valid_from"
        )
        assert len(rows) == 3
        old_id_1 = [r for r in rows if r[0] == 1 and r[3] == 0]
        assert len(old_id_1) == 1
        assert old_id_1[0][1] == "EU"
        assert old_id_1[0][2] is not None
        new_id_1 = [r for r in rows if r[0] == 1 and r[3] == 1]
        assert len(new_id_1) == 1
        assert new_id_1[0][1] == "APAC"
        assert new_id_1[0][2] is None
        id_2 = [r for r in rows if r[0] == 2]
        assert len(id_2) == 1
        assert id_2[0][3] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self, **kwargs: Any) -> ScdType2:
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
            return ScdType2(**defaults, _config=KnotConfig(id="scd2"))

    async def _call(self, k: ScdType2, **overrides: Any) -> Any:
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
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaises(TypeError):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, source_query="")

    async def test_rejects_pk_outside_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, primary_keys=("orphan",))

    async def test_rejects_invalid_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, effective_date_column="not a name")

    async def test_rejects_scd_column_in_column_names(self) -> None:
        k = self._make_knot()
        with self.assertRaises(ValueError):
            await self._call(k, column_names=("id", "name", "valid_from"))
