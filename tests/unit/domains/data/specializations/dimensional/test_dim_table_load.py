"""Tests for :class:`DimTableLoad`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.dim_table_load import (
    DimTableLoad,
)
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
        self._tmp_target_pool_type1 = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool_type1.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "dim1.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  dim_sk INTEGER PRIMARY KEY,"
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        self.target_pool_type1 = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool_type1.close()
        
        
        self._tmp_target_pool_type1.cleanup()
    def test_rejects_non_pool(self) -> None:
        target_pool_type1 = self.target_pool_type1
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            DimTableLoad(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool_type1,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                _config=KnotConfig(id="dim"),
            )

    def test_rejects_invalid_scd_type(self) -> None:
        source_pool = self.source_pool
        target_pool_type1 = self.target_pool_type1
        with self.assertRaisesRegex(ValueError, "scd_type"):
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool_type1,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                scd_type=3,  # type: ignore[arg-type]
                _config=KnotConfig(id="dim"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        source_pool = self.source_pool
        target_pool_type1 = self.target_pool_type1
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool_type1,
                target_table="bad table",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                _config=KnotConfig(id="dim"),
            )


class TestDimTableLoadType1(unittest.IsolatedAsyncioTestCase):

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
        self._tmp_target_pool_type1 = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool_type1.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "dim1.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  dim_sk INTEGER PRIMARY KEY,"
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )
        self.target_pool_type1 = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool_type1.close()
        
        
        self._tmp_target_pool_type1.cleanup()
    async def test_inserts_with_surrogate_keys(self) -> None:
        source_pool = self.source_pool
        target_pool_type1 = self.target_pool_type1
        with Tapestry() as t:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type1,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                _config=KnotConfig(id="dim"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool_type1.fetch_all(
            "SELECT dim_sk, id, name, region FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        assert rows[0][0] == 1
        assert rows[1][0] == 2

    async def test_updates_on_second_run(self) -> None:
        source_pool = self.source_pool
        target_pool_type1 = self.target_pool_type1
        with Tapestry() as t:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type1,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                _config=KnotConfig(id="dim"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type1,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                _config=KnotConfig(id="dim"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool_type1.fetch_all(
            "SELECT region FROM customers WHERE id = 1"
        )
        assert rows[0][0] == "APAC"
        count = await target_pool_type1.fetch_all(
            "SELECT COUNT(*) FROM customers"
        )
        assert count[0][0] == 2


class TestDimTableLoadType2(unittest.IsolatedAsyncioTestCase):

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
        self._tmp_target_pool_type2 = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool_type2.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "dim2.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  dim_sk INTEGER NOT NULL,"
            "  id INTEGER NOT NULL,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL,"
            "  valid_from TEXT NOT NULL,"
            "  valid_to TEXT,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        self.target_pool_type2 = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool_type2.close()
        
        
        self._tmp_target_pool_type2.cleanup()
    async def test_inserts_with_history_columns(self) -> None:
        source_pool = self.source_pool
        target_pool_type2 = self.target_pool_type2
        with Tapestry() as t:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type2,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                scd_type=2,
                _config=KnotConfig(id="dim2"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool_type2.fetch_all(
            "SELECT id, valid_to, is_current FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[1] is None
            assert row[2] == 1

    async def test_expires_old_row_on_change(self) -> None:
        source_pool = self.source_pool
        target_pool_type2 = self.target_pool_type2
        with Tapestry() as t:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type2,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                scd_type=2,
                _config=KnotConfig(id="dim2"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            DimTableLoad(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool_type2,
                target_table="customers",
                natural_key_columns=("id",),
                non_key_columns=("name", "region"),
                scd_type=2,
                _config=KnotConfig(id="dim2"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool_type2.fetch_all(
            "SELECT id, region, is_current FROM customers ORDER BY id, valid_from"
        )
        assert len(rows) == 3
        old_alice = [r for r in rows if r[0] == 1 and r[2] == 0][0]
        assert old_alice[1] == "EU"
        new_alice = [r for r in rows if r[0] == 1 and r[2] == 1][0]
        assert new_alice[1] == "APAC"
