"""Tests for :class:`GoldAggregation`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.medallion.gold_aggregation import (
    GoldAggregation,
)
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT region, amount FROM silver_sales ORDER BY region"
_SOURCE_COLUMNS = ["region", "amount"]
_TARGET_TABLE = "gold_sales"
_BY = ["region"]
_AGGS = {"total": AggregateSpec(source="amount", function="sum")}


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE silver_sales (region TEXT, amount REAL)"
    )
    await src.execute_many(
        "INSERT INTO silver_sales (region, amount) VALUES (?, ?)",
        [("East", 100.0), ("East", 50.0), ("West", 200.0)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute("CREATE TABLE gold_sales (region TEXT, total REAL)")
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> GoldAggregation:
    return GoldAggregation(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        source_columns=_SOURCE_COLUMNS,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        by=_BY,
        aggs=_AGGS,
        _config=KnotConfig(id="gold"),
    )


class TestGoldAggregation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_aggregates_and_writes_gold(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT region, total FROM gold_sales ORDER BY region"
        )
        rows_dict = {r: t for r, t in rows}
        assert rows_dict["East"] == 150.0
        assert rows_dict["West"] == 200.0

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["succeeded"] is True
        assert out["rows_inserted"] == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        src, tgt = self.src, self.tgt

        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q = emit_query(_config=KnotConfig(id="q"))
            GoldAggregation(
                source_pool=src,
                source_query=q,
                source_columns=_SOURCE_COLUMNS,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                by=_BY,
                aggs=_AGGS,
                _config=KnotConfig(id="gold"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["gold"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> GoldAggregation:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "source_columns": _SOURCE_COLUMNS,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "by": _BY,
            "aggs": _AGGS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return GoldAggregation(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: GoldAggregation, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "source_columns": _SOURCE_COLUMNS,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "by": _BY,
            "aggs": _AGGS,
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

    async def test_rejects_empty_source_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_columns"):
            await self._call(k, source_columns=[])

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "by"):
            await self._call(k, by=[])
