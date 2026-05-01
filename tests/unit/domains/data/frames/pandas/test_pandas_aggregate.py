"""Tests for :class:`PandasAggregate`."""

from __future__ import annotations

import pandas as pd
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_aggregate import PandasAggregate
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame(
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, None],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            }
        )
    )


@pytest.mark.asyncio
class TestPandasAggregate:
    async def test_sum_per_region(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PandasAggregate(
                batch=batch,
                by=("region",),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["agg"]
        totals = dict(zip(out.frame["region"].tolist(), out.frame["total"].tolist()))
        assert totals["EU"] == 40.0
        assert totals["US"] == 100.0

    async def test_multiple_aggregations(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            PandasAggregate(
                batch=batch,
                by=("region",),
                aggs={
                    "total": AggregateSpec(source="amount", function="sum"),
                    "avg": AggregateSpec(source="amount", function="mean"),
                    "n_customers": AggregateSpec(
                        source="customer", function="count_distinct"
                    ),
                },
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["agg"]
        eu = out.frame[out.frame["region"] == "EU"].iloc[0].to_dict()
        assert eu["total"] == 40.0
        assert eu["avg"] == pytest.approx(40.0 / 3)
        assert eu["n_customers"] == 2

    async def test_composite_group_by(self) -> None:
        @knot
        async def two_dim() -> PandasDataBatch:
            return PandasDataBatch(
                frame=pd.DataFrame(
                    {
                        "region": ["EU", "EU", "EU", "US"],
                        "tier":   ["A", "B", "A", "A"],
                        "amount": [1, 2, 3, 4],
                    }
                )
            )

        with Tapestry() as t:
            batch = two_dim(_config=KnotConfig(id="orders"))
            PandasAggregate(
                batch=batch,
                by=("region", "tier"),
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["agg"]
        assert out.row_count == 3


class TestConstruction:
    def test_rejects_non_spec_in_aggs(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="AggregateSpec"):
                PandasAggregate(
                    batch=batch,
                    by=("a",),
                    aggs={"total": "sum(amount)"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_empty_by(self) -> None:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                PandasAggregate(
                    batch=batch,
                    by=(),
                    aggs={"total": AggregateSpec(source="x", function="sum")},
                    _config=KnotConfig(id="a"),
                )
