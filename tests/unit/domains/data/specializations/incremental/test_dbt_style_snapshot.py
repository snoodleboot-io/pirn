"""Tests for :class:`DbtStyleSnapshot`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.dbt_style_snapshot import (
    DbtStyleSnapshot,
)
from pirn.tapestry import Tapestry


def make_knot(
    source_pool: SqlitePool, target_pool: SqlitePool
) -> DbtStyleSnapshot:
    return DbtStyleSnapshot(
        source_pool=source_pool,
        source_query="SELECT id, status FROM orders ORDER BY id",
        target_pool=target_pool,
        target_table="orders_snapshot",
        key_columns=("id",),
        tracked_columns=("status",),
        _config=KnotConfig(id="snap"),
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
        )
        await pool.execute_many(
            "INSERT INTO orders (id, status) VALUES (?, ?)",
            [(1, "pending"), (2, "shipped")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE orders_snapshot ("
            "  id INTEGER NOT NULL,"
            "  status TEXT NOT NULL,"
            "  dbt_valid_from TEXT NOT NULL,"
            "  dbt_valid_to TEXT,"
            "  dbt_is_current INTEGER NOT NULL,"
            "  dbt_scd_id TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            DbtStyleSnapshot(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="orders_snapshot",
                key_columns=("id",),
                tracked_columns=("status",),
                _config=KnotConfig(id="snap"),
            )

    def test_rejects_overlapping_columns(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "overlap"):
            DbtStyleSnapshot(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="orders_snapshot",
                key_columns=("id", "status"),
                tracked_columns=("status",),
                _config=KnotConfig(id="snap"),
            )


class TestDbtStyleSnapshotBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
        )
        await pool.execute_many(
            "INSERT INTO orders (id, status) VALUES (?, ?)",
            [(1, "pending"), (2, "shipped")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE orders_snapshot ("
            "  id INTEGER NOT NULL,"
            "  status TEXT NOT NULL,"
            "  dbt_valid_from TEXT NOT NULL,"
            "  dbt_valid_to TEXT,"
            "  dbt_is_current INTEGER NOT NULL,"
            "  dbt_scd_id TEXT NOT NULL"
            ")"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_first_run_inserts_all_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id FROM orders_snapshot WHERE dbt_is_current = 1 ORDER BY id"
        )
        assert [r[0] for r in rows] == [1, 2]

    async def test_unchanged_rows_are_not_duplicated(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        for _ in range(2):
            with Tapestry() as t:
                make_knot(source_pool, target_pool)
            await t.run(RunRequest())
        rows = await target_pool.fetch_all(
            "SELECT COUNT(*) FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 1"
        )
        assert rows[0][0] == 1

    async def test_changed_row_closes_old_and_inserts_new(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute(
            "UPDATE orders SET status = ? WHERE id = ?", ("delivered", 1)
        )
        with Tapestry() as t2:
            make_knot(source_pool, target_pool)
        result = await t2.run(RunRequest())
        assert result.succeeded
        current = await target_pool.fetch_all(
            "SELECT status FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 1"
        )
        assert current[0][0] == "delivered"
        closed = await target_pool.fetch_all(
            "SELECT COUNT(*) FROM orders_snapshot WHERE id = 1 AND dbt_is_current = 0"
        )
        assert closed[0][0] == 1

    async def test_result_tracks_inserted_and_closed(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            knot = make_knot(source_pool, target_pool)
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["rows_inserted"] == 2
        assert out["rows_closed"] == 0
