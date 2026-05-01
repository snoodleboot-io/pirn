"""Tests for :class:`DataBatchToPyarrow`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pyarrow.bridges.data_batch_to_pyarrow import (
    DataBatchToPyarrow,
)
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
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


@pytest.mark.asyncio
class TestDataBatchToPyarrow:
    async def test_constructs_table_from_rows(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPyarrow(batch=batch, _config=KnotConfig(id="arrow"))
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["arrow"]
        assert set(out.column_names) == {"id", "name"}
        assert out.row_count == 2

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPyarrow(batch=batch, _config=KnotConfig(id="arrow"))
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["arrow"]
        assert out.source_uri == "memory://users"

    async def test_empty_batch_yields_empty_table(self) -> None:
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="empty"))
            DataBatchToPyarrow(batch=batch, _config=KnotConfig(id="arrow"))
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["arrow"]
        assert out.row_count == 0
