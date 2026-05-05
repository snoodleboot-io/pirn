"""Tests for :class:`MergeUpsert`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.merge_upsert import MergeUpsert
from pirn.tapestry import Tapestry


def make_knot(
    source_pool: SqlitePool, target_pool: SqlitePool
) -> MergeUpsert:
    return MergeUpsert(
        source_pool=source_pool,
        source_query="SELECT id, name, dept FROM employees ORDER BY id",
        target_pool=target_pool,
        target_table="employees",
        key_columns=("id",),
        non_key_columns=("name", "dept"),
        _config=KnotConfig(id="upsert"),
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
        )
        await pool.execute_many(
            "INSERT INTO employees (id, name, dept) VALUES (?, ?, ?)",
            [(1, "Alice", "Eng"), (2, "Bob", "Sales")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            MergeUpsert(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="employees",
                key_columns=("id",),
                non_key_columns=("name",),
                _config=KnotConfig(id="upsert"),
            )

    def test_rejects_overlapping_columns(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "overlap"):
            MergeUpsert(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="employees",
                key_columns=("id", "name"),
                non_key_columns=("name", "dept"),
                _config=KnotConfig(id="upsert"),
            )

    def test_rejects_empty_source_query(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "source_query"):
            MergeUpsert(
                source_pool=source_pool,
                source_query="",
                target_pool=target_pool,
                target_table="employees",
                key_columns=("id",),
                non_key_columns=("name",),
                _config=KnotConfig(id="upsert"),
            )


class TestMergeUpsertBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
        )
        await pool.execute_many(
            "INSERT INTO employees (id, name, dept) VALUES (?, ?, ?)",
            [(1, "Alice", "Eng"), (2, "Bob", "Sales")],
        )
        self.source_pool = pool
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
        )
        self.target_pool = pool

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_inserts_new_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, dept FROM employees ORDER BY id"
        )
        assert rows == [(1, "Alice", "Eng"), (2, "Bob", "Sales")]

    async def test_updates_changed_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute(
            "UPDATE employees SET dept = ? WHERE id = ?", ("Finance", 1)
        )
        with Tapestry() as t2:
            make_knot(source_pool, target_pool)
        await t2.run(RunRequest())
        rows = await target_pool.fetch_all(
            "SELECT id, dept FROM employees ORDER BY id"
        )
        assert rows == [(1, "Finance"), (2, "Sales")]

    async def test_does_not_delete_removed_rows(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute("DELETE FROM employees WHERE id = 2")
        with Tapestry() as t2:
            MergeUpsert(
                source_pool=source_pool,
                source_query="SELECT id, name, dept FROM employees ORDER BY id",
                target_pool=target_pool,
                target_table="employees",
                key_columns=("id",),
                non_key_columns=("name", "dept"),
                _config=KnotConfig(id="upsert"),
            )
        await t2.run(RunRequest())
        count = await target_pool.fetch_all("SELECT COUNT(*) FROM employees")
        assert count[0][0] == 2

    async def test_result_tracks_inserted_and_updated(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            knot = make_knot(source_pool, target_pool)
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["rows_inserted"] == 2
        assert out["rows_updated"] == 0
