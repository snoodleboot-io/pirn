"""Tests for :class:`PolarsDataBatch`."""

from __future__ import annotations

import unittest

try:
    import polars  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("polars not installed") from _e
from datetime import UTC

import polars as pl
from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch


class TestPolarsDataBatch(unittest.TestCase):
    def test_row_count_and_columns_reflect_frame(self) -> None:
        frame = pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        batch = PolarsDataBatch(frame=frame, source_uri="memory://test")
        assert batch.row_count == 3
        assert batch.column_names == ("id", "name")

    def test_default_fetched_at_is_utc(self) -> None:
        batch = PolarsDataBatch(frame=pl.DataFrame())
        assert batch.fetched_at.tzinfo is UTC

    def test_with_frame_preserves_metadata(self) -> None:
        original = PolarsDataBatch(
            frame=pl.DataFrame({"x": [1]}),
            source_uri="postgres://h/db",
        )
        replaced = original.with_frame(pl.DataFrame({"x": [1, 2, 3]}))
        assert replaced.row_count == 3
        assert replaced.source_uri == original.source_uri
        assert replaced.fetched_at == original.fetched_at

    def test_dataclass_is_frozen(self) -> None:
        batch = PolarsDataBatch(frame=pl.DataFrame())
        try:
            batch.frame = pl.DataFrame()  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("expected FrozenInstanceError")
