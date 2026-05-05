"""Tests for :class:`SparkDataFrame`."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


def _mock_frame(columns: list) -> MagicMock:
    frame = MagicMock()
    frame.columns = columns
    return frame


class TestSparkDataFrame(unittest.TestCase):
    def test_construction_defaults(self) -> None:
        frame = _mock_frame(["a", "b"])
        sdf = SparkDataFrame(frame=frame)
        self.assertEqual(sdf.backend_name, "spark")
        self.assertEqual(sdf.source_uri, "")
        self.assertIsInstance(sdf.fetched_at, datetime)

    def test_column_names(self) -> None:
        frame = _mock_frame(["x", "y", "z"])
        sdf = SparkDataFrame(frame=frame)
        self.assertEqual(sdf.column_names, ("x", "y", "z"))

    def test_with_frame_preserves_metadata(self) -> None:
        frame = _mock_frame(["a"])
        now = datetime.now(timezone.utc)
        sdf = SparkDataFrame(frame=frame, backend_name="custom", source_uri="s3://b", fetched_at=now)
        new_frame = _mock_frame(["b"])
        sdf2 = sdf.with_frame(new_frame)
        self.assertEqual(sdf2.backend_name, "custom")
        self.assertEqual(sdf2.source_uri, "s3://b")
        self.assertEqual(sdf2.fetched_at, now)

    def test_frozen(self) -> None:
        frame = _mock_frame(["a"])
        sdf = SparkDataFrame(frame=frame)
        with self.assertRaises((AttributeError, TypeError)):
            sdf.backend_name = "other"  # type: ignore[misc]
