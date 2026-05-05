"""Tests for :class:`DuckdbAggregate`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_aggregate import DuckdbAggregate
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES "
        "('EU', 10.0, 'alice'), "
        "('EU', 25.0, 'bob'), "
        "('EU', 5.0,  'alice'), "
        "('US', 100.0,'carol'), "
        "('US', NULL, 'carol')"
        ") AS v(region, amount, customer)"
    )
    return DuckdbDataBatch(
        relation=connection.table("t"), connection=connection
    )


class TestDuckdbAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_sum_per_region(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DuckdbAggregate(
                batch=batch,
                by=("region",),
                aggs={"total": "SUM(amount)"},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["agg"]
        rows = out.relation.fetchall()
        totals = {row[0]: row[1] for row in rows}
        assert totals["EU"] == 40.0
        assert totals["US"] == 100.0

    async def test_multiple_aggregations(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DuckdbAggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "total": "SUM(amount)",
                    "n_customers": "COUNT(DISTINCT customer)",
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["agg"]
        rows = out.relation.fetchall()
        # Columns are ordered: region, total, n_customers
        eu = next(row for row in rows if row[0] == "EU")
        assert eu[1] == 40.0
        assert eu[2] == 2

    async def test_composite_group_by(self) -> None:
        @knot
        async def two_dim() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            connection.execute(
                "CREATE TABLE t AS "
                "SELECT * FROM (VALUES "
                "('EU', 'A', 1), "
                "('EU', 'B', 2), "
                "('EU', 'A', 3), "
                "('US', 'A', 4)"
                ") AS v(region, tier, amount)"
            )
            return DuckdbDataBatch(
                relation=connection.table("t"), connection=connection
            )

        with Tapestry() as t:
            batch = two_dim(_config=KnotConfig(id="orders"))
            DuckdbAggregate(
                batch=batch,
                by=("region", "tier"),
                aggs={"total": "SUM(amount)"},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["agg"]
        rows = out.relation.fetchall()
        assert len(rows) == 3


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string_aggs(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "SQL expression"):
                DuckdbAggregate(
                    batch=batch, by=("a",),
                    aggs={"total": 123},  # type: ignore[dict-item]
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_by(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                DuckdbAggregate(
                    batch=batch, by=(),
                    aggs={"total": "SUM(x)"},
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_injection_in_expression(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "forbidden"):
                DuckdbAggregate(
                    batch=batch, by=("a",),
                    aggs={"total": "SUM(x); DROP TABLE t"},
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_unsafe_output_name(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "plain identifier"):
                DuckdbAggregate(
                    batch=batch, by=("a",),
                    aggs={"bad name!": "SUM(x)"},
                    _config=KnotConfig(id="a"),
                )
