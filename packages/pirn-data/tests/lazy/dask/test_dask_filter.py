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
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry
from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn_data.lazy.dask.dask_filter import DaskFilter


def _make_batch(data: dict) -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame(data), npartitions=1)
    return DaskDataFrame(frame=frame)


@knot
async def emit_batch() -> DaskDataFrame:
    return _make_batch({"x": [1, 2, 3]})


class TestDaskFilter(unittest.IsolatedAsyncioTestCase):
    async def test_filters_rows(self) -> None:
        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            DaskFilter(
                batch=batch,
                predicate=lambda f: f["x"] > 1,
                _config=KnotConfig(id="flt"),
            )
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["flt"]
        df = out.frame.compute()
        assert len(df) == 2
        assert (df["x"] > 1).all()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_predicate() -> Any:
            return lambda f: f["x"] > 2

        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            pred = emit_predicate(_config=KnotConfig(id="pred"))
            DaskFilter(batch=batch, predicate=pred, _config=KnotConfig(id="flt"))
        result = await t.run(RunRequest())
        out: DaskDataFrame = result.outputs["flt"]
        df = out.frame.compute()
        assert len(df) == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DaskFilter:
        class _Src(Source):
            async def process(self, **_: Any) -> DaskDataFrame:
                return _make_batch({"x": [1]})

        with Tapestry():
            src = _Src(_config=KnotConfig(id="src"))
            return DaskFilter(batch=src, _config=KnotConfig(id="flt"), **kwargs)

    async def test_rejects_non_callable_predicate(self) -> None:
        k = self._make_knot(predicate="not-callable")
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=_make_batch({"x": [1]}),
                predicate="not-callable",
            )
