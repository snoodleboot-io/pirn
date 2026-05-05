"""Tests for :class:`FullRefreshExtract`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.full_refresh_extract import (
    FullRefreshExtract,
)
from pirn.tapestry import Tapestry


class TestFullRefreshExtract(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL)")
        await pool.execute_many(
            "INSERT INTO products (id, sku) VALUES (?, ?)",
            [(1, "A1"), (2, "A2"), (3, "A3")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL)")
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_loads_into_empty_target(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            FullRefreshExtract(
                source_pool=source_pool,
                source_query="SELECT id, sku FROM products ORDER BY id",
                target_pool=target_pool,
                target_table="products",
                insert_query="INSERT INTO products (id, sku) VALUES (?, ?)",
                _config=KnotConfig(id="refresh"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, [(r.knot_id, r.outcome) for r in result.lineage]
        rows = await target_pool.fetch_all("SELECT id, sku FROM products ORDER BY id")
        assert rows == [(1, "A1"), (2, "A2"), (3, "A3")]

    async def test_subsequent_run_drops_and_reloads(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        await target_pool.execute_many(
            "INSERT INTO products (id, sku) VALUES (?, ?)",
            [(99, "STALE")],
        )
        with Tapestry() as t:
            FullRefreshExtract(
                source_pool=source_pool,
                source_query="SELECT id, sku FROM products ORDER BY id",
                target_pool=target_pool,
                target_table="products",
                insert_query="INSERT INTO products (id, sku) VALUES (?, ?)",
                _config=KnotConfig(id="refresh"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all("SELECT id FROM products ORDER BY id")
        assert rows == [(1,), (2,), (3,)]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            FullRefreshExtract(
                source_pool=object(),  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=object(),  # type: ignore[arg-type]
                target_table="t",
                insert_query="INSERT INTO t VALUES (?)",
                _config=KnotConfig(id="x"),
            )
