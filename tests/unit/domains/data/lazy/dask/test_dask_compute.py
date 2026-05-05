"""Tests for :class:`DaskCompute`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

try:
    import dask.dataframe as dd
    import pandas as pd
except ImportError as _e:
    raise unittest.SkipTest("dask not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_compute import DaskCompute
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_execution_receipt import DaskExecutionReceipt
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _dask_batch() -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame({"x": [1, 2, 3]}), npartitions=1)
    return DaskDataFrame(frame=frame)


class _DaskSource(Source):
    async def process(self, **_: Any) -> DaskDataFrame:
        return _dask_batch()


class TestDaskComputeConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            dc = DaskCompute(batch=src, _config=KnotConfig(id="compute"))
        self.assertIsInstance(dc, DaskCompute)
        self.assertIsNone(dc.target_path)
        self.assertFalse(dc.return_pandas)

    def test_path_requires_writer(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskCompute(
                    batch=src,
                    target_path="/tmp/out",
                    _config=KnotConfig(id="compute"),
                )

    def test_return_pandas_exclusive_with_target_path(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            with self.assertRaises(TypeError):
                DaskCompute(
                    batch=src,
                    target_path="/tmp/out",
                    writer=lambda f, p: None,
                    return_pandas=True,
                    _config=KnotConfig(id="compute"),
                )


class TestDaskComputeProcess(unittest.IsolatedAsyncioTestCase):
    async def test_default_returns_receipt(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            dc = DaskCompute(batch=src, _config=KnotConfig(id="compute"))
        result = await dc.process(batch=_dask_batch())
        self.assertIsInstance(result, DaskExecutionReceipt)
        self.assertEqual(result.row_count, 3)

    async def test_return_pandas_returns_dataframe(self) -> None:
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            dc = DaskCompute(batch=src, return_pandas=True, _config=KnotConfig(id="compute"))
        result = await dc.process(batch=_dask_batch())
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)

    async def test_writer_mode_calls_writer(self) -> None:
        writer = MagicMock()
        with Tapestry():
            src = _DaskSource(_config=KnotConfig(id="src"))
            dc = DaskCompute(
                batch=src,
                target_path="/tmp/out",
                writer=writer,
                _config=KnotConfig(id="compute"),
            )
        result = await dc.process(batch=_dask_batch())
        writer.assert_called_once()
        self.assertIsInstance(result, DaskExecutionReceipt)
        self.assertEqual(result.target_path, "/tmp/out")
