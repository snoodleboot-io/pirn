"""Tests for :class:`PandasAggregate`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

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


def _empty_batch() -> PandasDataBatch:
    return PandasDataBatch(frame=pd.DataFrame({"a": [1]}))


class TestPandasAggregate(unittest.IsolatedAsyncioTestCase):
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
        totals = dict(zip(out.frame["region"].tolist(), out.frame["total"].tolist(), strict=False))
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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> object:
            return ("region",)

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            PandasAggregate(
                batch=batch,
                by=by_knot,
                aggs={"total": AggregateSpec(source="amount", function="sum")},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["agg"]
        assert "total" in out.frame.columns


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PandasAggregate:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame({"a": [1]}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PandasAggregate(
                batch=batch,
                by=("a",),
                aggs={"n": AggregateSpec(source="a", function="count")},
                _config=KnotConfig(id="agg"),
                **kwargs,
            )

    async def test_rejects_string_by(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(
                batch=_empty_batch(),
                by="region",
                aggs={"n": AggregateSpec(source="a", function="count")},
            )

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_empty_batch(),
                by=(),
                aggs={"n": AggregateSpec(source="a", function="count")},
            )

    async def test_rejects_non_spec_in_aggs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "AggregateSpec"):
            await k.process(
                batch=_empty_batch(),
                by=("a",),
                aggs={"total": "sum(amount)"},
            )

    async def test_rejects_empty_aggs(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(
                batch=_empty_batch(),
                by=("a",),
                aggs={},
            )
