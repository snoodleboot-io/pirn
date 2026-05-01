"""Tests for :class:`pirn.domains.data.transforms.aggregate.Aggregate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.transforms.aggregate import Aggregate
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec
from pirn.tapestry import Tapestry


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


@pytest.mark.asyncio
class TestAggregate:
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


class TestAggregateSpec:
    def test_rejects_unknown_function(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            AggregateSpec(source="amount", function="median")

    def test_rejects_empty_source(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            AggregateSpec(source="", function="sum")


class TestConstruction:
    def test_rejects_string_by(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="sequence"):
                Aggregate(
                    batch=batch, by="region",  # type: ignore[arg-type]
                    aggs={"x": AggregateSpec(source="a", function="sum")},
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_aggs(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="non-empty"):
                Aggregate(
                    batch=batch, by=("a",), aggs={},
                    _config=KnotConfig(id="a"),
                )
