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
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_compute import DaskCompute
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_execution_receipt import DaskExecutionReceipt
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


def _dask_batch() -> DaskDataFrame:
    frame = dd.from_pandas(pd.DataFrame({"x": [1, 2, 3]}), npartitions=1)
    return DaskDataFrame(frame=frame)


@knot
async def emit_batch() -> DaskDataFrame:
    return _dask_batch()


class TestDaskCompute(unittest.IsolatedAsyncioTestCase):
    async def test_default_returns_receipt(self) -> None:
        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            DaskCompute(batch=batch, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())
        out = result.outputs["sink"]
        assert isinstance(out, DaskExecutionReceipt)
        assert out.row_count == 3

    async def test_return_pandas(self) -> None:
        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            DaskCompute(batch=batch, return_pandas=True, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())
        out = result.outputs["sink"]
        assert isinstance(out, pd.DataFrame)
        assert len(out) == 3

    async def test_writer_mode_calls_writer(self) -> None:
        writer = MagicMock()
        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            DaskCompute(
                batch=batch,
                target_path="/tmp/out",
                writer=writer,
                _config=KnotConfig(id="sink"),
            )
        result = await t.run(RunRequest())
        writer.assert_called_once()
        out = result.outputs["sink"]
        assert isinstance(out, DaskExecutionReceipt)
        assert out.target_path == "/tmp/out"


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_return_pandas_from_knot(self) -> None:
        @knot
        async def emit_flag() -> bool:
            return True

        with Tapestry() as t:
            batch = emit_batch(_config=KnotConfig(id="batch"))
            flag = emit_flag(_config=KnotConfig(id="flag"))
            DaskCompute(batch=batch, return_pandas=flag, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())
        out = result.outputs["sink"]
        assert isinstance(out, pd.DataFrame)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> DaskCompute:
        class _Src(Source):
            async def process(self, **_: Any) -> DaskDataFrame:
                return _dask_batch()

        with Tapestry():
            src = _Src(_config=KnotConfig(id="src"))
            return DaskCompute(batch=src, _config=KnotConfig(id="sink"), **kwargs)

    async def test_rejects_empty_target_path(self) -> None:
        k = self._make_knot(target_path="path", writer=lambda f, p: None)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=_dask_batch(),
                target_path="",
                writer=lambda f, p: None,
                writer_kwargs=None,
                return_pandas=False,
            )

    async def test_rejects_target_path_without_writer(self) -> None:
        k = self._make_knot(target_path="/some/path", writer=lambda f, p: None)
        with self.assertRaisesRegex(TypeError, "writer is required"):
            await k.process(
                batch=_dask_batch(),
                target_path="/some/path",
                writer=None,
                writer_kwargs=None,
                return_pandas=False,
            )

    async def test_rejects_return_pandas_with_target_path(self) -> None:
        k = self._make_knot(target_path="/some/path", writer=lambda f, p: None)
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            await k.process(
                batch=_dask_batch(),
                target_path="/some/path",
                writer=lambda f, p: None,
                writer_kwargs=None,
                return_pandas=True,
            )
