"""Tests for :class:`ReconciliationDiff`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.reconciliation_diff import (
    ReconciliationDiff,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        await p.execute_many(
            "INSERT INTO records (id, value) VALUES (?, ?)",
            [(1, "alpha"), (2, "beta"), (3, "gamma")],
        )
        self.source_pool = p
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        await p.execute_many(
            "INSERT INTO records (id, value) VALUES (?, ?)",
            [(1, "alpha"), (2, "CHANGED"), (4, "delta")],
        )
        self.target_pool = p

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    def test_rejects_non_pool_source(self) -> None:
        target_pool = self.target_pool
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ReconciliationDiff(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_query="SELECT 1",
                key_columns=("id",),
                value_columns=("value",),
                _config=KnotConfig(id="diff"),
            )

    def test_rejects_overlapping_columns(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with self.assertRaisesRegex(ValueError, "overlap"):
            ReconciliationDiff(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_query="SELECT 1",
                key_columns=("id", "value"),
                value_columns=("value",),
                _config=KnotConfig(id="diff"),
            )


class TestReconciliationDiffBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        await p.execute_many(
            "INSERT INTO records (id, value) VALUES (?, ?)",
            [(1, "alpha"), (2, "beta"), (3, "gamma")],
        )
        self.source_pool = p
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        await p.execute_many(
            "INSERT INTO records (id, value) VALUES (?, ?)",
            [(1, "alpha"), (2, "CHANGED"), (4, "delta")],
        )
        self.target_pool = p

    async def asyncTearDown(self) -> None:
        await self.source_pool.close()
        
        
        await self.target_pool.close()
        
        
    async def test_classifies_added_removed_changed_matched(self) -> None:
        source_pool = self.source_pool
        target_pool = self.target_pool
        with Tapestry() as t:
            knot = ReconciliationDiff(
                source_pool=source_pool,
                source_query="SELECT id, value FROM records ORDER BY id",
                target_pool=target_pool,
                target_query="SELECT id, value FROM records ORDER BY id",
                key_columns=("id",),
                value_columns=("value",),
                _config=KnotConfig(id="diff"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert [3] in out["added"]
        assert [4] in out["removed"]
        assert [2] in out["changed"]
        assert out["matched"] == 1
        assert out["total_differences"] == 3

    async def test_identical_tables_have_no_differences(self) -> None:
        source_pool = self.source_pool
        with Tapestry() as t:
            knot = ReconciliationDiff(
                source_pool=source_pool,
                source_query="SELECT id, value FROM records ORDER BY id",
                target_pool=source_pool,
                target_query="SELECT id, value FROM records ORDER BY id",
                key_columns=("id",),
                value_columns=("value",),
                _config=KnotConfig(id="diff"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["total_differences"] == 0
        assert out["matched"] == 3
