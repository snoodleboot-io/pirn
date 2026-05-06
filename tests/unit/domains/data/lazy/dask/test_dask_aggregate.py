"""Tests for :class:`DaskAggregate`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import dask.dataframe as dd
    import pandas as pd
except ImportError as _e:
    raise unittest.SkipTest("dask not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_aggregate import DaskAggregate
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _make_batch(data: dict) -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame(data), npartitions=1)
    return DaskDataFrame(frame=frame)


@knot
async def emit_orders() -> DaskDataFrame:
    return _make_batch(
        {"region": ["EU", "EU", "US"], "amount": [10, 20, 5]}
    )


class TestDaskAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_declarative_sum(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DaskAggregate(
                batch=batch,
                by=["region"],
                aggs={"amount": "sum"},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["agg"]
        df = out.frame.compute()
        eu_total = int(df[df["region"] == "EU"]["amount"].iloc[0])
        assert eu_total == 30

    async def test_aggregator_callable(self) -> None:
        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            DaskAggregate(
                batch=batch,
                aggregator=lambda f: f.groupby("region")["amount"].sum().reset_index(),
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["agg"]
        df = out.frame.compute()
        assert len(df) == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        @knot
        async def emit_by() -> list:
            return ["region"]

        with Tapestry() as t:
            batch = emit_orders(_config=KnotConfig(id="orders"))
            by_knot = emit_by(_config=KnotConfig(id="by"))
            DaskAggregate(
                batch=batch,
                by=by_knot,
                aggs={"amount": "sum"},
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["agg"]
        df = out.frame.compute()
        assert "region" in df.columns


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DaskAggregate:
        class _Src(Source):
            async def process(self, **_: Any) -> DaskDataFrame:
                return _make_batch({"region": ["EU"], "amount": [10]})

        with Tapestry():
            src = _Src(_config=KnotConfig(id="src"))
            return DaskAggregate(batch=src, _config=KnotConfig(id="agg"), **kwargs)

    async def test_rejects_neither_aggregator_nor_by(self) -> None:
        k = self._make_knot(aggregator=None, by=None, aggs=None)
        with self.assertRaisesRegex(TypeError, "aggregator or"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                aggregator=None,
                by=None,
                aggs=None,
            )

    async def test_rejects_aggregator_with_by(self) -> None:
        k = self._make_knot(aggregator=lambda f: f, by=["x"], aggs=None)
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                aggregator=lambda f: f,
                by=["x"],
                aggs=None,
            )

    async def test_rejects_empty_by(self) -> None:
        k = self._make_knot(aggregator=None, by=[], aggs={"x": "sum"})
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                aggregator=None,
                by=[],
                aggs={"x": "sum"},
            )

    async def test_rejects_by_without_aggs(self) -> None:
        k = self._make_knot(aggregator=None, by=["x"], aggs=None)
        with self.assertRaisesRegex(TypeError, "aggs is required"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                aggregator=None,
                by=["x"],
                aggs=None,
            )

    async def test_rejects_non_callable_aggregator(self) -> None:
        k = self._make_knot(aggregator="bad", by=None, aggs=None)
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                aggregator="bad",
                by=None,
                aggs=None,
            )
