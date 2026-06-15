"""Tests for :class:`DaskDataFrame`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

try:
    import dask.dataframe as dd
    import pandas as pd
except ImportError as _e:
    raise unittest.SkipTest("dask not installed") from _e

from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame


def _make_dask_frame() -> dd.DataFrame:
    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    return dd.from_pandas(pdf, npartitions=1)


class TestDaskDataFrame(unittest.TestCase):
    def test_construction_defaults(self) -> None:
        frame = _make_dask_frame()
        ddf = DaskDataFrame(frame=frame)
        self.assertEqual(ddf.backend_name, "dask")
        self.assertEqual(ddf.source_uri, "")
        self.assertIsInstance(ddf.fetched_at, datetime)

    def test_column_names(self) -> None:
        frame = _make_dask_frame()
        ddf = DaskDataFrame(frame=frame)
        self.assertEqual(set(ddf.column_names), {"a", "b"})

    def test_npartitions(self) -> None:
        frame = _make_dask_frame()
        ddf = DaskDataFrame(frame=frame)
        self.assertEqual(ddf.npartitions, 1)

    def test_with_frame_preserves_metadata(self) -> None:
        frame = _make_dask_frame()
        now = datetime.now(UTC)
        ddf = DaskDataFrame(frame=frame, backend_name="custom", source_uri="s3://b/k", fetched_at=now)
        new_frame = _make_dask_frame()
        ddf2 = ddf.with_frame(new_frame)
        self.assertEqual(ddf2.backend_name, "custom")
        self.assertEqual(ddf2.source_uri, "s3://b/k")
        self.assertEqual(ddf2.fetched_at, now)

    def test_frozen(self) -> None:
        frame = _make_dask_frame()
        ddf = DaskDataFrame(frame=frame)
        with self.assertRaises((AttributeError, TypeError)):
            ddf.backend_name = "other"  # type: ignore[misc]
