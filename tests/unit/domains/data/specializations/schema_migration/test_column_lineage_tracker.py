"""Tests for :class:`ColumnLineageTracker`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.column_lineage_tracker import (
    ColumnLineageTracker,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE column_lineage_registry "
        "(source_table TEXT, source_column TEXT, transform_id TEXT, "
        "target_table TEXT, target_column TEXT, recorded_at TEXT)"
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ColumnLineageTracker(
                pool="bad",  # type: ignore[arg-type]
                source_table="src",
                target_table="tgt",
                transform_id="t1",
                column_mappings=[("a", "b")],
                _config=KnotConfig(id="clt"),
            )

    def test_rejects_empty_column_mappings(
        self, pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="column_mappings"):
            ColumnLineageTracker(
                pool=pool,
                source_table="src",
                target_table="tgt",
                transform_id="t1",
                column_mappings=[],
                _config=KnotConfig(id="clt"),
            )

    def test_rejects_invalid_column_name(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            ColumnLineageTracker(
                pool=pool,
                source_table="src",
                target_table="tgt",
                transform_id="t1",
                column_mappings=[("bad col", "b")],
                _config=KnotConfig(id="clt"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_records_all_mappings(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            ColumnLineageTracker(
                pool=pool,
                source_table="stg_orders",
                target_table="mart_revenue",
                transform_id="mart_knot",
                column_mappings=[("order_id", "order_id"), ("amount", "revenue")],
                _config=KnotConfig(id="clt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await pool.fetch_all(
            "SELECT source_table, source_column, target_table, target_column "
            "FROM column_lineage_registry ORDER BY source_column"
        )
        assert rows == [
            ("stg_orders", "amount", "mart_revenue", "revenue"),
            ("stg_orders", "order_id", "mart_revenue", "order_id"),
        ]

    async def test_returns_mappings_recorded_count(
        self, pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            ColumnLineageTracker(
                pool=pool,
                source_table="stg_orders",
                target_table="mart_revenue",
                transform_id="mart_knot",
                column_mappings=[("a", "x"), ("b", "y"), ("c", "z")],
                _config=KnotConfig(id="clt2"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["clt2"]["mappings_recorded"] == 3
