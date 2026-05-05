"""Tests for :class:`ScdType2`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_2 import ScdType2
from pirn.tapestry import Tapestry


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
        
        
        self._tmp_target_pool.cleanup()
    def test_rejects_non_pool(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ScdType2(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id", "name", "region"),
                _config=KnotConfig(id="scd2"),
            )

    def test_rejects_pk_outside_columns(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with pytest.raises(
            ValueError, match="primary_keys not in column_names"
        ):
            ScdType2(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("orphan",),
                column_names=("id", "name"),
                _config=KnotConfig(id="scd2"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ScdType2(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                primary_keys=("id",),
                column_names=("id",),
                effective_date_column="not a name",
                _config=KnotConfig(id="scd2"),
            )


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
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
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
        
        
        self._tmp_target_pool.cleanup()
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
        # First run.
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
        # Change one source row.
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        # Second run.
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
        # Three rows: id=1 has two versions (old + new); id=2 unchanged.
        assert len(rows) == 3
        # Old version of id=1 is expired.
        old_id_1 = [r for r in rows if r[0] == 1 and r[3] == 0]
        assert len(old_id_1) == 1
        assert old_id_1[0][1] == "EU"
        assert old_id_1[0][2] is not None
        # New version of id=1 is current.
        new_id_1 = [r for r in rows if r[0] == 1 and r[3] == 1]
        assert len(new_id_1) == 1
        assert new_id_1[0][1] == "APAC"
        assert new_id_1[0][2] is None
        # id=2 still has a single current row.
        id_2 = [r for r in rows if r[0] == 2]
        assert len(id_2) == 1
        assert id_2[0][3] == 1
