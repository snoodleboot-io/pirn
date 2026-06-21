"""Tests for :class:`DatafusionDataBatch`."""

from __future__ import annotations

import unittest

try:
    import datafusion  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("datafusion not installed") from _e
from datetime import UTC

import datafusion as df
from pirn_data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class TestDatafusionDataBatch(unittest.TestCase):
    def test_columns_reflect_frame(self) -> None:
        ctx = df.SessionContext()
        frame = ctx.from_pylist([{"id": 1, "name": "a"}])
        batch = DatafusionDataBatch(
            frame=frame, context=ctx, source_uri="memory://test"
        )
        assert set(batch.column_names) == {"id", "name"}

    def test_default_fetched_at_is_utc(self) -> None:
        ctx = df.SessionContext()
        frame = ctx.from_pylist([{"x": 1}])
        batch = DatafusionDataBatch(frame=frame, context=ctx)
        assert batch.fetched_at.tzinfo is UTC

    def test_with_frame_preserves_metadata(self) -> None:
        ctx = df.SessionContext()
        frame = ctx.from_pylist([{"x": 1}])
        original = DatafusionDataBatch(
            frame=frame, context=ctx, source_uri="postgres://h/db"
        )
        new_frame = ctx.from_pylist([{"x": 1}, {"x": 2}, {"x": 3}])
        replaced = original.with_frame(new_frame)
        assert replaced.context is original.context
        assert replaced.source_uri == original.source_uri
        assert replaced.fetched_at == original.fetched_at

    def test_dataclass_is_frozen(self) -> None:
        ctx = df.SessionContext()
        frame = ctx.from_pylist([{"x": 1}])
        batch = DatafusionDataBatch(frame=frame, context=ctx)
        try:
            batch.frame = frame  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("expected FrozenInstanceError")
