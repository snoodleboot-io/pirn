"""Tests for :class:`PandasDataBatch`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e
from datetime import UTC

import pandas as pd
from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


class TestPandasDataBatch(unittest.TestCase):
    def test_row_count_and_columns_reflect_frame(self) -> None:
        frame = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        batch = PandasDataBatch(frame=frame, source_uri="memory://test")
        assert batch.row_count == 3
        assert batch.column_names == ("id", "name")

    def test_default_fetched_at_is_utc(self) -> None:
        batch = PandasDataBatch(frame=pd.DataFrame())
        assert batch.fetched_at.tzinfo is UTC

    def test_with_frame_preserves_metadata(self) -> None:
        original = PandasDataBatch(
            frame=pd.DataFrame({"x": [1]}),
            source_uri="postgres://h/db",
        )
        replaced = original.with_frame(pd.DataFrame({"x": [1, 2, 3]}))
        assert replaced.row_count == 3
        assert replaced.source_uri == original.source_uri
        assert replaced.fetched_at == original.fetched_at

    def test_dataclass_is_frozen(self) -> None:
        batch = PandasDataBatch(frame=pd.DataFrame())
        try:
            batch.frame = pd.DataFrame()  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("expected FrozenInstanceError")
