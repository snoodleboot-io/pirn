"""Tests for :class:`DataBatchToPolars`."""

from __future__ import annotations

import unittest

try:
    import polars  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("polars not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.bridges.data_batch_to_polars import (
    DataBatchToPolars,
)
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DataBatch:
    rows = (
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
    )
    return DataBatch(rows=rows, source_uri="memory://users")


@knot
async def emit_empty() -> DataBatch:
    return DataBatch()


class TestDataBatchToPolars(unittest.IsolatedAsyncioTestCase):
    async def test_constructs_polars_frame_from_rows(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPolars(batch=batch, _config=KnotConfig(id="polars"))
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["polars"]
        assert out.row_count == 2
        assert set(out.column_names) == {"id", "name"}

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPolars(batch=batch, _config=KnotConfig(id="polars"))
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["polars"]
        assert out.source_uri == "memory://users"

    async def test_empty_batch_yields_empty_frame(self) -> None:
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="empty"))
            DataBatchToPolars(batch=batch, _config=KnotConfig(id="polars"))
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["polars"]
        assert out.row_count == 0
