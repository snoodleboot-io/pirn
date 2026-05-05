"""Tests for :class:`ReferentialIntegrityCheck`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.referential_integrity_check import (
    ReferentialIntegrityCheck,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"
        )
        await p.execute_many(
            "INSERT INTO customers (id, name) VALUES (?, ?)",
            [(1, "Alice"), (2, "Bob")],
        )
        await p.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER)"
        )
        await p.execute_many(
            "INSERT INTO orders (id, customer_id) VALUES (?, ?)",
            [(1, 1), (2, 2), (3, 99)],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ReferentialIntegrityCheck(
                pool="bad",  # type: ignore[arg-type]
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )

    def test_rejects_invalid_fact_table(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ReferentialIntegrityCheck(
                pool=pool,
                fact_table="bad table",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )


class TestReferentialIntegrityCheckBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"
        )
        await p.execute_many(
            "INSERT INTO customers (id, name) VALUES (?, ?)",
            [(1, "Alice"), (2, "Bob")],
        )
        await p.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER)"
        )
        await p.execute_many(
            "INSERT INTO orders (id, customer_id) VALUES (?, ?)",
            [(1, 1), (2, 2), (3, 99)],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_detects_orphaned_rows(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            knot = ReferentialIntegrityCheck(
                pool=pool,
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["orphaned_rows"] == 1
        assert out["has_orphans"] is True
        assert abs(out["orphaned_pct"] - 100 / 3) < 0.01

    async def test_clean_table_has_no_orphans(self) -> None:
        pool = self.pool
        await pool.execute("DELETE FROM orders WHERE id = 3")
        with Tapestry() as t:
            knot = ReferentialIntegrityCheck(
                pool=pool,
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["orphaned_rows"] == 0
        assert out["has_orphans"] is False
