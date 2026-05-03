"""Tests for :class:`MartModelKnot`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.mart_model_knot import (
    MartModelKnot,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE int_orders "
        "(order_id INTEGER, region TEXT, amount REAL)"
    )
    await p.execute(
        "CREATE TABLE mart_revenue (region TEXT, total_revenue REAL)"
    )
    await p.execute_many(
        "INSERT INTO int_orders VALUES (?, ?, ?)",
        [(1, "EU", 100.0), (2, "EU", 50.0), (3, "US", 200.0)],
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_empty_metric_expressions(
        self, pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="metric_expressions"):
            MartModelKnot(
                source_pool=pool,
                source_table="int_orders",
                group_by_columns=["region"],
                metric_expressions=[],
                target_pool=pool,
                target_table="mart_revenue",
                _config=KnotConfig(id="mart"),
            )

    def test_rejects_invalid_table_identifier(
        self, pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            MartModelKnot(
                source_pool=pool,
                source_table="int orders",
                group_by_columns=["region"],
                metric_expressions=["SUM(amount)"],
                target_pool=pool,
                target_table="mart_revenue",
                _config=KnotConfig(id="mart"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_aggregates_by_group(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            MartModelKnot(
                source_pool=pool,
                source_table="int_orders",
                group_by_columns=["region"],
                metric_expressions=["SUM(amount) AS total_revenue"],
                target_pool=pool,
                target_table="mart_revenue",
                _config=KnotConfig(id="mart"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await pool.fetch_all(
            "SELECT region, total_revenue FROM mart_revenue ORDER BY region"
        )
        assert rows == [("EU", 150.0), ("US", 200.0)]

    async def test_no_group_by_aggregates_all(self, pool: SqlitePool) -> None:
        await pool.execute(
            "CREATE TABLE mart_totals (grand_total REAL)"
        )
        with Tapestry() as t:
            MartModelKnot(
                source_pool=pool,
                source_table="int_orders",
                group_by_columns=[],
                metric_expressions=["SUM(amount) AS grand_total"],
                target_pool=pool,
                target_table="mart_totals",
                _config=KnotConfig(id="mart-total"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await pool.fetch_all("SELECT grand_total FROM mart_totals")
        assert rows == [(350.0,)]
