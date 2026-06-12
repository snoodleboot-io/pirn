"""Tests for :class:`MartModelKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.mart_model_knot import (
    MartModelKnot,
)
from pirn.tapestry import Tapestry

_SOURCE_TABLE = "int_orders"
_GROUP_BY_COLUMNS = ("region",)
_METRIC_EXPRESSIONS = ("SUM(amount) AS total_revenue",)
_TARGET_TABLE = "mart_revenue"


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE int_orders (order_id INTEGER, region TEXT, amount REAL)"
    )
    await p.execute("CREATE TABLE mart_revenue (region TEXT, total_revenue REAL)")
    await p.execute_many(
        "INSERT INTO int_orders VALUES (?, ?, ?)",
        [(1, "EU", 100.0), (2, "EU", 50.0), (3, "US", 200.0)],
    )
    return p


def _make_knot(pool: SqlitePool) -> MartModelKnot:
    return MartModelKnot(
        source_pool=pool,
        source_table=_SOURCE_TABLE,
        group_by_columns=_GROUP_BY_COLUMNS,
        metric_expressions=_METRIC_EXPRESSIONS,
        target_pool=pool,
        target_table=_TARGET_TABLE,
        _config=KnotConfig(id="mart"),
    )


class TestMartModelKnot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_aggregates_by_group(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT region, total_revenue FROM mart_revenue ORDER BY region"
        )
        assert rows == [("EU", 150.0), ("US", 200.0)]

    async def test_no_group_by_aggregates_all(self) -> None:
        await self.pool.execute("CREATE TABLE mart_totals (grand_total REAL)")
        with Tapestry() as t:
            MartModelKnot(
                source_pool=self.pool,
                source_table=_SOURCE_TABLE,
                group_by_columns=(),
                metric_expressions=("SUM(amount) AS grand_total",),
                target_pool=self.pool,
                target_table="mart_totals",
                _config=KnotConfig(id="mart-total"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all("SELECT grand_total FROM mart_totals")
        assert rows == [(350.0,)]

    async def test_returns_rows_written(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["rows_written"] == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_source_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_table() -> str:
            return _SOURCE_TABLE

        with Tapestry() as t:
            tbl_knot = emit_table(_config=KnotConfig(id="tbl"))
            MartModelKnot(
                source_pool=self.pool,
                source_table=tbl_knot,
                group_by_columns=_GROUP_BY_COLUMNS,
                metric_expressions=_METRIC_EXPRESSIONS,
                target_pool=self.pool,
                target_table=_TARGET_TABLE,
                _config=KnotConfig(id="mart"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mart"]["rows_written"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> MartModelKnot:
        defaults: dict[str, Any] = {
            "source_pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "group_by_columns": _GROUP_BY_COLUMNS,
            "metric_expressions": _METRIC_EXPRESSIONS,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return MartModelKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: MartModelKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "group_by_columns": _GROUP_BY_COLUMNS,
            "metric_expressions": _METRIC_EXPRESSIONS,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_metric_expressions(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "metric_expressions"):
            await self._call(k, metric_expressions=())

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, source_table="int orders")
