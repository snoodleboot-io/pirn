"""Tests for :class:`FactTableLoad`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.fact_table_load import (
    FactTableLoad,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE sales ("
            "  sale_id INTEGER PRIMARY KEY,"
            "  customer_id INTEGER NOT NULL,"
            "  amount REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO sales (sale_id, customer_id, amount) VALUES (?, ?, ?)",
            [(1, 10, 99.99), (2, 20, 149.50), (3, 99, 25.00)],
        )
        self.source_pool = pool
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "fact.db")))
        await pool.execute(
            "CREATE TABLE fact_sales ("
            "  sale_id INTEGER NOT NULL,"
            "  amount REAL NOT NULL,"
            "  customer_sk INTEGER NOT NULL"
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
            FactTableLoad(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="fact_sales",
                source_columns=("sale_id", "customer_id", "amount"),
                fact_columns=("sale_id", "amount"),
                dim_lookups=[
                    {
                        "dim_table": "customers",
                        "natural_key_columns": ("customer_id",),
                        "surrogate_key_column": "customer_sk",
                        "fact_fk_column": "customer_sk",
                    }
                ],
                _config=KnotConfig(id="fact"),
            )

    def test_rejects_empty_dim_lookups(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "dim_lookups"):
            FactTableLoad(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="fact_sales",
                source_columns=("sale_id",),
                fact_columns=("sale_id",),
                dim_lookups=[],
                _config=KnotConfig(id="fact"),
            )

    def test_rejects_missing_required_lookup_key(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "missing key"):
            FactTableLoad(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="fact_sales",
                source_columns=("sale_id",),
                fact_columns=("sale_id",),
                dim_lookups=[{"dim_table": "customers"}],
                _config=KnotConfig(id="fact"),
            )


class TestFactTableLoadBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp_dim_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_dim_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "dim.db")))
        await pool.execute(
            "CREATE TABLE customers ("
            "  customer_sk INTEGER PRIMARY KEY,"
            "  customer_id INTEGER NOT NULL,"
            "  is_current INTEGER NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO customers (customer_sk, customer_id, is_current) VALUES (?, ?, ?)",
            [(1001, 10, 1), (1002, 20, 1)],
        )
        self.dim_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE sales ("
            "  sale_id INTEGER PRIMARY KEY,"
            "  customer_id INTEGER NOT NULL,"
            "  amount REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO sales (sale_id, customer_id, amount) VALUES (?, ?, ?)",
            [(1, 10, 99.99), (2, 20, 149.50), (3, 99, 25.00)],
        )
        self.source_pool = pool
        self._tmp_target_pool = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_target_pool.name)
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "fact.db")))
        await pool.execute(
            "CREATE TABLE fact_sales ("
            "  sale_id INTEGER NOT NULL,"
            "  amount REAL NOT NULL,"
            "  customer_sk INTEGER NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.dim_pool.close()
        
        
        self._tmp_dim_pool.cleanup()
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
        self._tmp_target_pool.cleanup()
    async def test_resolves_dimension_keys(self) -> None:
        source_pool = self.source_pool
        dim_pool = self.dim_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            FactTableLoad(
                source_pool=source_pool,
                source_query="SELECT sale_id, customer_id, amount FROM sales",
                target_pool=target_pool,
                target_table="fact_sales",
                source_columns=("sale_id", "customer_id", "amount"),
                fact_columns=("sale_id", "amount"),
                dim_lookups=[
                    {
                        "dim_table": "customers",
                        "dim_pool": dim_pool,
                        "natural_key_columns": ("customer_id",),
                        "surrogate_key_column": "customer_sk",
                        "fact_fk_column": "customer_sk",
                        "is_current_column": "is_current",
                    }
                ],
                _config=KnotConfig(id="fact"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT sale_id, customer_sk FROM fact_sales ORDER BY sale_id"
        )
        assert len(rows) == 3
        sk_map = {r[0]: r[1] for r in rows}
        assert sk_map[1] == 1001
        assert sk_map[2] == 1002

    async def test_late_arriving_dim_uses_unknown_sk(self) -> None:
        source_pool = self.source_pool
        dim_pool = self.dim_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            FactTableLoad(
                source_pool=source_pool,
                source_query="SELECT sale_id, customer_id, amount FROM sales",
                target_pool=target_pool,
                target_table="fact_sales",
                source_columns=("sale_id", "customer_id", "amount"),
                fact_columns=("sale_id", "amount"),
                dim_lookups=[
                    {
                        "dim_table": "customers",
                        "dim_pool": dim_pool,
                        "natural_key_columns": ("customer_id",),
                        "surrogate_key_column": "customer_sk",
                        "fact_fk_column": "customer_sk",
                        "is_current_column": "is_current",
                    }
                ],
                unknown_sk=-1,
                _config=KnotConfig(id="fact"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT sale_id, customer_sk FROM fact_sales WHERE sale_id = 3"
        )
        assert rows[0][1] == -1
