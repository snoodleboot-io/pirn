"""Tests for :class:`DaskSource`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

try:
    import dask.dataframe as dd
    import pandas as pd
except ImportError as _e:
    raise unittest.SkipTest("dask not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn_data.lazy.dask.dask_source import DaskSource


def _make_frame() -> dd.DataFrame:
    return dd.from_pandas(pd.DataFrame({"x": [1, 2]}), npartitions=1)


class TestDaskSourceConstruction(unittest.TestCase):
    def test_factory_mode(self) -> None:
        src = DaskSource(factory=_make_frame, _config=KnotConfig(id="src"))
        self.assertIsInstance(src, DaskSource)

    def test_path_mode(self) -> None:
        src = DaskSource(
            path="/tmp/data.parquet",
            reader=lambda p: _make_frame(),
            _config=KnotConfig(id="src"),
        )
        self.assertIsInstance(src, DaskSource)


class TestDaskSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_factory_emits_dask_dataframe(self) -> None:
        src = DaskSource(factory=_make_frame, _config=KnotConfig(id="src"))
        result = await src.process(factory=_make_frame)
        self.assertIsInstance(result, DaskDataFrame)

    async def test_path_reader_called(self) -> None:
        frame = _make_frame()
        reader = MagicMock(return_value=frame)
        src = DaskSource(
            path="/tmp/data.parquet",
            reader=reader,
            _config=KnotConfig(id="src"),
        )
        result = await src.process(path="/tmp/data.parquet", reader=reader)
        reader.assert_called_once_with("/tmp/data.parquet")
        self.assertIsInstance(result, DaskDataFrame)

    async def test_rejects_neither_factory_nor_path(self) -> None:
        src = DaskSource(factory=_make_frame, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process()

    async def test_rejects_both_factory_and_path(self) -> None:
        src = DaskSource(factory=_make_frame, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process(factory=_make_frame, path="/tmp/data.parquet", reader=lambda p: _make_frame())

    async def test_path_without_reader_raises(self) -> None:
        src = DaskSource(factory=_make_frame, _config=KnotConfig(id="src"))
        with self.assertRaises(TypeError):
            await src.process(path="/tmp/data.parquet")

    async def test_source_uri_defaults_to_path(self) -> None:
        frame = _make_frame()
        reader = MagicMock(return_value=frame)
        src = DaskSource(
            path="/tmp/data.parquet",
            reader=reader,
            _config=KnotConfig(id="src"),
        )
        result = await src.process(path="/tmp/data.parquet", reader=reader)
        self.assertEqual(result.source_uri, "/tmp/data.parquet")
