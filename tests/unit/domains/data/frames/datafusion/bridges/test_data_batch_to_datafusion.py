"""Tests for :class:`DataBatchToDatafusion`."""

from __future__ import annotations

import unittest

try:
    import datafusion as df
except ImportError:
    raise unittest.SkipTest("datafusion not installed")

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.frames.datafusion.bridges.data_batch_to_datafusion import (
    DataBatchToDatafusion,
)
from pirn_data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn_data.frames.datafusion.datafusion_session_context_knot import (
    DatafusionSessionContextKnot,
)


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


class TestDataBatchToDatafusion(unittest.IsolatedAsyncioTestCase):
    async def test_constructs_frame_from_rows(self) -> None:
        with Tapestry() as t:
            ctx = DatafusionSessionContextKnot(_config=KnotConfig(id="ctx"))
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDatafusion(batch=batch, context=ctx, _config=KnotConfig(id="dfn"))
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["dfn"]
        assert set(out.column_names) == {"id", "name"}
        assert len(out.frame.to_pylist()) == 2

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            ctx = DatafusionSessionContextKnot(_config=KnotConfig(id="ctx"))
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDatafusion(batch=batch, context=ctx, _config=KnotConfig(id="dfn"))
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["dfn"]
        assert out.source_uri == "memory://users"

    async def test_empty_batch_yields_zero_rows(self) -> None:
        with Tapestry() as t:
            ctx = DatafusionSessionContextKnot(_config=KnotConfig(id="ctx"))
            batch = emit_empty(_config=KnotConfig(id="empty"))
            DataBatchToDatafusion(batch=batch, context=ctx, _config=KnotConfig(id="dfn"))
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["dfn"]
        assert out.frame.to_pylist() == []

    async def test_context_is_datafusion_session_context(self) -> None:
        with Tapestry() as t:
            ctx_knot = DatafusionSessionContextKnot(_config=KnotConfig(id="ctx"))
            batch = emit_users(_config=KnotConfig(id="users"))
            DataBatchToDatafusion(batch=batch, context=ctx_knot, _config=KnotConfig(id="dfn"))
        result = await t.run(RunRequest())
        out: DatafusionDataBatch = result.outputs["dfn"]
        # The bridge unwraps DatafusionSessionContext.ctx into DatafusionDataBatch.context.
        assert isinstance(out.context, df.SessionContext)
