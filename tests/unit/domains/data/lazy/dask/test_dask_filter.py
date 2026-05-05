"""Tests for :class:`DaskFilter`."""

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
from pirn.domains.data.lazy.dask.dask_filter import DaskFilter
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _make_batch(data: dict) -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame(data), npartitions=1)
    return DaskDataFrame(frame=frame)


class _DaskSource(Source):
    async def process(self, **_: Any) -> DaskDataFrame:
        return _make_batch({"x": [1, 2, 3]})


class TestDaskFilterConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            flt = DaskFilter(
                batch=src,
                predicate=lambda frame: frame["x"] > 1,
                _config=KnotConfig(id="flt"),
            )
        self.assertIsInstance(flt, DaskFilter)

    def test_rejects_non_callable_predicate(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskFilter(
                    batch=src,
                    predicate="not-callable",  # type: ignore[arg-type]
                    _config=KnotConfig(id="flt"),
                )


class TestDaskFilterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_filters_rows(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            flt = DaskFilter(
                batch=src,
                predicate=lambda f: f["x"] > 1,
                _config=KnotConfig(id="flt"),
            )
        result = await flt.process(batch=_make_batch({"x": [1, 2, 3]}))
        self.assertIsInstance(result, DaskDataFrame)
        df = result.frame.compute()
        self.assertEqual(len(df), 2)
        self.assertTrue((df["x"] > 1).all())
