"""Tests for :class:`ScdType5MiniDimWithCurrent`."""

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
from pirn_data.specializations.scd.scd_type_5_mini_dim_with_current import (
    ScdType5MiniDimWithCurrent,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_main_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_main_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main5.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  mini_dim_sk INTEGER,"
            "  current_mini_dim_sk INTEGER"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id) VALUES (?)",
            [(1,), (2,)],
        )
        self.main_pool = pool
        self._tmp_mini_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_mini_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini5.db")))
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
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, income_band, credit_score) VALUES (?, ?, ?)",
            [(1, "high", 800), (2, "low", 600)],
        )
        self.source_pool = pool

    async def asyncTearDown(self) -> None:
        await self.main_pool.close()
        self._tmp_main_pool.cleanup()
        await self.mini_pool.close()
        self._tmp_mini_pool.cleanup()
        await self.source_pool.close()

    def _make_knot(self, **kwargs: Any) -> ScdType5MiniDimWithCurrent:
        defaults: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, income_band, credit_score FROM customers",
            "main_pool": self.main_pool,
            "main_table": "customers",
            "main_key_columns": ("id",),
            "fact_fk_column": "mini_dim_sk",
            "current_mini_dim_sk_column": "current_mini_dim_sk",
            "mini_pool": self.mini_pool,
            "mini_table": "customer_profile",
            "mini_dim_attributes": ("income_band", "credit_score"),
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType5MiniDimWithCurrent(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ScdType5MiniDimWithCurrent, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.source_pool,
            "source_query": "SELECT id, income_band, credit_score FROM customers",
            "main_pool": self.main_pool,
            "main_table": "customers",
            "main_key_columns": ("id",),
            "fact_fk_column": "mini_dim_sk",
            "current_mini_dim_sk_column": "current_mini_dim_sk",
            "mini_pool": self.mini_pool,
            "mini_table": "customer_profile",
            "mini_dim_attributes": ("income_band", "credit_score"),
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_invalid_current_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, current_mini_dim_sk_column="bad column")


class TestScdType5Behaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_main_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_main_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main5.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  id INTEGER PRIMARY KEY,"
            "  mini_dim_sk INTEGER,"
            "  current_mini_dim_sk INTEGER"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id) VALUES (?)",
            [(1,), (2,)],
        )
        self.main_pool = pool
        self._tmp_mini_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_mini_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini5.db")))
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
            "  income_band TEXT NOT NULL,"
            "  credit_score INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (id, income_band, credit_score) VALUES (?, ?, ?)",
            [(1, "high", 800), (2, "low", 600)],
        )
        self.source_pool = pool

    async def asyncTearDown(self) -> None:
        await self.main_pool.close()
        self._tmp_main_pool.cleanup()
        await self.mini_pool.close()
        self._tmp_mini_pool.cleanup()
        await self.source_pool.close()

    async def test_sets_both_fk_and_current_sk(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with Tapestry() as t:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await main_pool.fetch_all(
            "SELECT id, mini_dim_sk, current_mini_dim_sk FROM customers ORDER BY id"
        )
        for row in rows:
            assert row[1] is not None
            assert row[2] is not None
            assert row[1] == row[2]

    async def test_reuses_mini_dim_rows(self) -> None:
        source_pool = self.source_pool
        main_pool = self.main_pool
        mini_pool = self.mini_pool
        with Tapestry() as t:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        assert (await t2.run(RunRequest())).succeeded
        count = await mini_pool.fetch_all("SELECT COUNT(*) FROM customer_profile")
        assert count[0][0] == 2
