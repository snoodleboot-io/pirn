"""Tests for :class:`pirn_data.transforms.aggregate.Aggregate`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.transforms.aggregate import Aggregate
from pirn_data.transforms.aggregate_spec import AggregateSpec


@knot
async def emit_orders() -> DataBatch:
    rows = (
        {"region": "EU", "amount": 10.0,  "customer": "alice"},
        {"region": "EU", "amount": 25.0,  "customer": "bob"},
        {"region": "EU", "amount": 5.0,   "customer": "alice"},
        {"region": "US", "amount": 100.0, "customer": "carol"},
        {"region": "US", "amount": None,  "customer": "carol"},
    )
    return DataBatch(rows=rows)


def _row_by_region(rows: tuple[dict, ...], region: str) -> dict:
    return next(r for r in rows if r["region"] == region)


def _make_batch() -> DataBatch:
    rows = (
        {"region": "EU", "amount": 10.0, "customer": "alice"},
        {"region": "EU", "amount": 25.0, "customer": "bob"},
        {"region": "US", "amount": 100.0, "customer": "carol"},
    )
    return DataBatch(rows=rows)


class TestAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_sum_per_group(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region",),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        assert _row_by_region(out.rows, "EU")["total"] == 40.0
        assert _row_by_region(out.rows, "US")["total"] == 100.0

    async def test_mean_skips_nulls(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region",),
                aggs={"avg": AggregateSpec(source="amount", function="mean")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        # EU: (10+25+5)/3 = 13.333...
        assert _row_by_region(out.rows, "EU")["avg"] == pytest.approx(40.0 / 3)
        # US: only one non-null = 100
        assert _row_by_region(out.rows, "US")["avg"] == 100.0

    async def test_count_and_count_distinct(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "n_orders":   AggregateSpec(source="amount",   function="count"),
                    "n_customers": AggregateSpec(source="customer", function="count_distinct"),
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        eu = _row_by_region(out.rows, "EU")
        assert eu["n_orders"] == 3        # 3 non-null amounts
        assert eu["n_customers"] == 2      # alice, bob
        us = _row_by_region(out.rows, "US")
        assert us["n_orders"] == 1
        assert us["n_customers"] == 1

    async def test_min_max_first_last(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "lo":    AggregateSpec(source="amount", function="min"),
                    "hi":    AggregateSpec(source="amount", function="max"),
                    "first": AggregateSpec(source="amount", function="first"),
                    "last":  AggregateSpec(source="amount", function="last"),
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        eu = _row_by_region(out.rows, "EU")
        assert eu["lo"] == 5.0
        assert eu["hi"] == 25.0
        assert eu["first"] == 10.0
        assert eu["last"] == 5.0

    async def test_composite_group_by(self) -> None:
        @knot
        async def two_dim() -> DataBatch:
            rows = (
                {"region": "EU", "tier": "A", "amount": 1},
                {"region": "EU", "tier": "B", "amount": 2},
                {"region": "EU", "tier": "A", "amount": 3},
                {"region": "US", "tier": "A", "amount": 4},
            )
            return DataBatch(rows=rows)

        with Tapestry() as t:
            batch = two_dim(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region", "tier"),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        # 3 groups: (EU,A)=4, (EU,B)=2, (US,A)=4
        groups = {(r["region"], r["tier"]): r["total"] for r in out.rows}
        assert groups == {("EU", "A"): 4, ("EU", "B"): 2, ("US", "A"): 4}

    async def test_schema_reflects_new_shape(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            Aggregate(
                batch=batch,
                by=("region",),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        assert out.schema.column_names == ("region", "total")
        assert out.schema.primary_keys == ("region",)


class TestAggregateSpec(unittest.TestCase):
    def test_rejects_unknown_function(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be one of"):
            AggregateSpec(source="amount", function="median")

    def test_rejects_empty_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            AggregateSpec(source="", function="sum")


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> tuple:
            return ("region",)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            Aggregate(
                batch=batch,
                by=by_knot,
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["agg"]
        assert _row_by_region(out.rows, "EU")["total"] == 40.0


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> Aggregate:
        @knot
        async def upstream() -> DataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return Aggregate(
                batch=batch,
                by=("region",),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
                **kwargs,
            )

    async def test_rejects_string_by(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(
                batch=_make_batch(),
                by="region",
                aggs={"total": AggregateSpec(source="amount", function="sum")},
            )

    async def test_rejects_empty_by(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_batch(),
                by=(),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), by=("region",), aggs={})

    async def test_rejects_non_aggregate_spec(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "AggregateSpec"):
            await k.process(
                batch=_make_batch(),
                by=("region",),
                aggs={"total": "sum"},  # type: ignore[arg-type]
            )
