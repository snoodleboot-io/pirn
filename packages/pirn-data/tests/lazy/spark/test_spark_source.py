"""Tests for :class:`SparkSource`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame

try:
    import pyspark.sql  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyspark not installed") from _e

from pirn_data.lazy.spark.spark_source import SparkSource


def _mock_session(frame: MagicMock | None = None) -> MagicMock:
    session = MagicMock()
    if frame is None:
        frame = MagicMock()
        frame.columns = ["a", "b"]
    session.sql.return_value = frame
    reader = MagicMock()
    reader.format.return_value = reader
    reader.options.return_value = reader
    reader.load.return_value = frame
    session.read = reader
    return session


class TestSparkSourceConstruction(unittest.TestCase):
    def test_path_mode(self) -> None:
        session = _mock_session()
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            path="/tmp/data.parquet",
        )
        self.assertIsInstance(src, SparkSource)

    def test_query_mode(self) -> None:
        session = _mock_session()
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            query="SELECT 1",
        )
        self.assertIsInstance(src, SparkSource)


class TestSparkSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_query_mode_emits_spark_dataframe(self) -> None:
        mock_frame = MagicMock()
        mock_frame.columns = ["id"]
        session = _mock_session(frame=mock_frame)
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            query="SELECT 1 AS id",
        )
        result = await src.process(spark_session=session, query="SELECT 1 AS id")
        self.assertIsInstance(result, SparkDataFrame)
        session.sql.assert_called_once_with("SELECT 1 AS id")

    async def test_path_mode_emits_spark_dataframe(self) -> None:
        mock_frame = MagicMock()
        mock_frame.columns = ["x"]
        session = _mock_session(frame=mock_frame)
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            path="/tmp/data.parquet",
        )
        result = await src.process(spark_session=session, path="/tmp/data.parquet")
        self.assertIsInstance(result, SparkDataFrame)

    async def test_rejects_no_session(self) -> None:
        session = _mock_session()
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            query="SELECT 1",
        )
        with self.assertRaises(TypeError):
            await src.process(spark_session=None, query="SELECT 1")

    async def test_rejects_neither_path_nor_query(self) -> None:
        session = _mock_session()
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            query="SELECT 1",
        )
        with self.assertRaises(TypeError):
            await src.process(spark_session=session)

    async def test_rejects_both(self) -> None:
        session = _mock_session()
        src = SparkSource(
            _config=KnotConfig(id="src"),
            spark_session=session,
            query="SELECT 1",
        )
        with self.assertRaises(TypeError):
            await src.process(spark_session=session, path="/tmp/data", query="SELECT 1")
