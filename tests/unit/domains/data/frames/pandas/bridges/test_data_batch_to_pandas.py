"""Tests for :class:`DataBatchToPandas`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.bridges.data_batch_to_pandas import (
    DataBatchToPandas,
)
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
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
class TestDataBatchToPandas:
    async def test_constructs_pandas_frame_from_rows(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPandas(batch=batch, _config=KnotConfig(id="pandas"))
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["pandas"]
        assert out.row_count == 2
        assert set(out.column_names) == {"id", "name"}

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToPandas(batch=batch, _config=KnotConfig(id="pandas"))
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["pandas"]
        assert out.source_uri == "memory://users"

    async def test_empty_batch_yields_empty_frame(self) -> None:
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="empty"))
            DataBatchToPandas(batch=batch, _config=KnotConfig(id="pandas"))
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["pandas"]
        assert out.row_count == 0
