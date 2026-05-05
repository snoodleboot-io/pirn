"""Tests for :class:`ScdType4MiniDimension`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_4_mini_dimension import (
    ScdType4MiniDimension,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_main_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_main_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  mini_dim_sk INTEGER"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name) VALUES (?, ?)",
            [(1, "Alice"), (2, "Bob")],
        )
        self.main_pool = pool
        self._tmp_mini_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_mini_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini.db")))
        await pool.execute(
            "CREATE TABLE customer_profile ("
            "  mini_dim_sk INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        self.mini_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name, income_band, credit_score) VALUES (?, ?, ?, ?)",
            [(1, "Alice", "high", 800), (2, "Bob", "low", 600)],
        )
        self.source_pool = pool

    async def asyncTearDown(self) -> None:
        await self.main_pool.close()
        
        
        self._tmp_main_pool.cleanup()
        await self.mini_pool.close()
        
        
        self._tmp_mini_pool.cleanup()
        await self.source_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ScdType4MiniDimension(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )

    def test_rejects_empty_source_query(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with self.assertRaisesRegex(ValueError, "source_query"):
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="bad table",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )


class TestScdType4Behaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_main_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_main_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  mini_dim_sk INTEGER"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name) VALUES (?, ?)",
            [(1, "Alice"), (2, "Bob")],
        )
        self.main_pool = pool
        self._tmp_mini_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_mini_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini.db")))
        await pool.execute(
            "CREATE TABLE customer_profile ("
            "  mini_dim_sk INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        self.mini_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, name, income_band, credit_score) VALUES (?, ?, ?, ?)",
            [(1, "Alice", "high", 800), (2, "Bob", "low", 600)],
        )
        self.source_pool = pool

    async def asyncTearDown(self) -> None:
        await self.main_pool.close()
        
        
        self._tmp_main_pool.cleanup()
        await self.mini_pool.close()
        
        
        self._tmp_mini_pool.cleanup()
        await self.source_pool.close()
        
        
    async def test_inserts_new_mini_dim_rows(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        mini_rows = await mini_pool.fetch_all(
            "SELECT income_band, credit_score FROM customer_profile ORDER BY mini_dim_sk"
        )
        assert len(mini_rows) == 2
        assert ("high", 800) in mini_rows
        assert ("low", 600) in mini_rows

    async def test_reuses_existing_mini_dim_rows(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t2.run(RunRequest())).succeeded
        mini_count = await mini_pool.fetch_all(
            "SELECT COUNT(*) FROM customer_profile"
        )
        assert mini_count[0][0] == 2

    async def test_updates_main_dim_fk(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t.run(RunRequest())).succeeded
        fk_rows = await main_pool.fetch_all(
            "SELECT id, mini_dim_sk FROM customers ORDER BY id"
        )
        for row in fk_rows:
            assert row[1] is not None
