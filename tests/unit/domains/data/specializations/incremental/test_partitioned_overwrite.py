"""Tests for :class:`PartitionedOverwrite`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.partitioned_overwrite import (
    PartitionedOverwrite,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE facts ("
            "  event_date TEXT NOT NULL,"
            "  metric TEXT NOT NULL,"
            "  value REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
            [
                ("2024-01-01", "clicks", 999.0),
                ("2024-01-01", "views", 888.0),
            ],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE facts ("
            "  event_date TEXT NOT NULL,"
            "  metric TEXT NOT NULL,"
            "  value REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
            [
                ("2024-01-01", "clicks", 100.0),
                ("2024-01-01", "views", 200.0),
                ("2024-01-02", "clicks", 50.0),
            ],
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            PartitionedOverwrite(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="facts",
                partition_column="event_date",
                partition_value="2024-01-01",
                source_columns=("event_date", "metric", "value"),
                _config=KnotConfig(id="po"),
            )

    def test_rejects_invalid_partition_column(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            PartitionedOverwrite(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="facts",
                partition_column="event date",
                partition_value="2024-01-01",
                source_columns=("event_date", "metric", "value"),
                _config=KnotConfig(id="po"),
            )


class TestPartitionedOverwriteBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE facts ("
            "  event_date TEXT NOT NULL,"
            "  metric TEXT NOT NULL,"
            "  value REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
            [
                ("2024-01-01", "clicks", 999.0),
                ("2024-01-01", "views", 888.0),
            ],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE facts ("
            "  event_date TEXT NOT NULL,"
            "  metric TEXT NOT NULL,"
            "  value REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
            [
                ("2024-01-01", "clicks", 100.0),
                ("2024-01-01", "views", 200.0),
                ("2024-01-02", "clicks", 50.0),
            ],
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_overwrites_only_target_partition(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            PartitionedOverwrite(
                source_pool=source_pool,
                source_query=(
                    "SELECT event_date, metric, value FROM facts "
                    "WHERE event_date = '2024-01-01'"
                ),
                target_pool=target_pool,
                target_table="facts",
                partition_column="event_date",
                partition_value="2024-01-01",
                source_columns=("event_date", "metric", "value"),
                _config=KnotConfig(id="po"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        partition_rows = await target_pool.fetch_all(
            "SELECT metric, value FROM facts WHERE event_date = '2024-01-01' ORDER BY metric"
        )
        assert set(r[0] for r in partition_rows) == {"clicks", "views"}
        assert any(abs(r[1] - 999.0) < 0.01 for r in partition_rows if r[0] == "clicks")
        other_rows = await target_pool.fetch_all(
            "SELECT metric FROM facts WHERE event_date = '2024-01-02'"
        )
        assert len(other_rows) == 1

    async def test_result_contains_rows_inserted(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            knot = PartitionedOverwrite(
                source_pool=source_pool,
                source_query=(
                    "SELECT event_date, metric, value FROM facts "
                    "WHERE event_date = '2024-01-01'"
                ),
                target_pool=target_pool,
                target_table="facts",
                partition_column="event_date",
                partition_value="2024-01-01",
                source_columns=("event_date", "metric", "value"),
                _config=KnotConfig(id="po"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["rows_inserted"] == 2
