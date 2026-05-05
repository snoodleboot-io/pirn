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
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_aggregate import DaskAggregate
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _make_batch(data: dict) -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame(data), npartitions=1)
    return DaskDataFrame(frame=frame)


class _DaskSource(Source):
    async def process(self, **_: Any) -> DaskDataFrame:
        return _make_batch({"region": ["EU"], "amount": [10]})


class TestDaskAggregateConstruction(unittest.TestCase):
    def test_aggregator_mode(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            agg = DaskAggregate(
                batch=src,
                aggregator=lambda f: f.groupby("region")["amount"].sum().reset_index(),
                _config=KnotConfig(id="agg"),
            )
        self.assertIsInstance(agg, DaskAggregate)

    def test_declarative_mode(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            agg = DaskAggregate(
                batch=src,
                by=["region"],
                aggs={"amount": "sum"},
                _config=KnotConfig(id="agg"),
            )
        self.assertEqual(agg.by, ("region",))

    def test_rejects_neither_aggregator_nor_by(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskAggregate(batch=src, _config=KnotConfig(id="agg"))

    def test_rejects_aggregator_with_by(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskAggregate(
                    batch=src,
                    aggregator=lambda f: f,
                    by=["region"],
                    _config=KnotConfig(id="agg"),
                )

    def test_rejects_by_without_aggs(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskAggregate(batch=src, by=["region"], _config=KnotConfig(id="agg"))

    def test_rejects_empty_by(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(ValueError):
                DaskAggregate(batch=src, by=[], aggs={"amount": "sum"}, _config=KnotConfig(id="agg"))


class TestDaskAggregateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_declarative_aggregation(self) -> None:
        batch = _make_batch({"region": ["EU", "EU", "US"], "amount": [10, 20, 5]})
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            agg = DaskAggregate(
                batch=src,
                by=["region"],
                aggs={"amount": "sum"},
                _config=KnotConfig(id="agg"),
            )
        result = await agg.process(batch=batch)
        self.assertIsInstance(result, DaskDataFrame)
        df = result.frame.compute().sort_values("region").reset_index(drop=True)
        eu_row = df[df["region"] == "EU"]
        self.assertEqual(int(eu_row["amount"].iloc[0]), 30)
