"""Tests for :class:`PyarrowDataBatch`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e
from datetime import UTC

import pyarrow as pa
from pirn_data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class TestPyarrowDataBatch(unittest.TestCase):
    def test_row_count_and_columns_reflect_table(self) -> None:
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        batch = PyarrowDataBatch(table=table, source_uri="memory://test")
        assert batch.row_count == 3
        assert batch.column_names == ("id", "name")

    def test_default_fetched_at_is_utc(self) -> None:
        batch = PyarrowDataBatch(table=pa.table({}))
        assert batch.fetched_at.tzinfo is UTC

    def test_with_table_preserves_metadata(self) -> None:
        original = PyarrowDataBatch(
            table=pa.table({"x": [1]}),
            source_uri="postgres://h/db",
        )
        replaced = original.with_table(pa.table({"x": [1, 2, 3]}))
        assert replaced.row_count == 3
        assert replaced.source_uri == original.source_uri
        assert replaced.fetched_at == original.fetched_at

    def test_dataclass_is_frozen(self) -> None:
        batch = PyarrowDataBatch(table=pa.table({}))
        try:
            batch.table = pa.table({})  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("expected FrozenInstanceError")
