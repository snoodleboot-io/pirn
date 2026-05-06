"""Tests for :class:`ColumnLineageTracker`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.column_lineage_tracker import (
    ColumnLineageTracker,
)
from pirn.tapestry import Tapestry

_LINEAGE_TABLE = "column_lineage_registry"
_CREATE_SQL = (
    f"CREATE TABLE {_LINEAGE_TABLE} "
    "(source_table TEXT, source_column TEXT, transform_id TEXT, "
    "target_table TEXT, target_column TEXT, recorded_at TEXT)"
)


async def _make_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(_CREATE_SQL)
    return pool


def _make_knot(pool: SqlitePool, **overrides: Any) -> ColumnLineageTracker:
    defaults: dict[str, Any] = {
        "pool": pool,
        "source_table": "stg_orders",
        "target_table": "mart_revenue",
        "transform_id": "mart_knot",
        "column_mappings": [("order_id", "order_id"), ("amount", "revenue")],
        "_config": KnotConfig(id="clt"),
    }
    defaults.update(overrides)
    return ColumnLineageTracker(**defaults)


class TestColumnLineageTracker(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_records_all_mappings(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT source_table, source_column, target_table, target_column "
            f"FROM {_LINEAGE_TABLE} ORDER BY source_column"
        )
        assert rows == [
            ("stg_orders", "amount", "mart_revenue", "revenue"),
            ("stg_orders", "order_id", "mart_revenue", "order_id"),
        ]

    async def test_returns_mappings_recorded_count(self) -> None:
        with Tapestry() as t:
            _make_knot(
                self.pool,
                column_mappings=[("a", "x"), ("b", "y"), ("c", "z")],
                _config=KnotConfig(id="clt2"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["clt2"]["mappings_recorded"] == 3

    async def test_custom_lineage_table(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE custom_lineage "
            "(source_table TEXT, source_column TEXT, transform_id TEXT, "
            "target_table TEXT, target_column TEXT, recorded_at TEXT)"
        )
        with Tapestry() as t:
            _make_knot(
                pool,
                lineage_table="custom_lineage",
                column_mappings=[("x", "y")],
                _config=KnotConfig(id="clt-custom"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["clt-custom"]["lineage_table"] == "custom_lineage"
        await pool.close()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_transform_id_from_upstream_knot(self) -> None:
        @knot
        async def emit_id() -> str:
            return "wired_transform"

        with Tapestry() as t:
            tid_knot = emit_id(_config=KnotConfig(id="tid"))
            ColumnLineageTracker(
                pool=self.pool,
                source_table="src",
                target_table="tgt",
                transform_id=tid_knot,
                column_mappings=[("a", "b")],
                _config=KnotConfig(id="clt-wire"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["clt-wire"]["mappings_recorded"] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> ColumnLineageTracker:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "source_table": "stg_orders",
            "target_table": "mart_revenue",
            "transform_id": "mart_knot",
            "column_mappings": [("order_id", "order_id")],
        }
        defaults.update(kwargs)
        with Tapestry():
            return ColumnLineageTracker(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ColumnLineageTracker, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "source_table": "stg_orders",
            "target_table": "mart_revenue",
            "transform_id": "mart_knot",
            "column_mappings": [("order_id", "order_id")],
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_column_mappings(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_mappings"):
            await self._call(k, column_mappings=[])

    async def test_rejects_invalid_column_name(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, column_mappings=[("bad col", "b")])

    async def test_rejects_invalid_source_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, source_table="bad table")
