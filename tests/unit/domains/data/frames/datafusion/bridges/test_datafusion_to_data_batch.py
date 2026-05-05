"""Tests for :class:`DatafusionToDataBatch`."""

from __future__ import annotations
import unittest

import datafusion as df

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.datafusion.bridges.datafusion_to_data_batch import (
    DatafusionToDataBatch,
)
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.tapestry import Tapestry


@knot
async def emit_dfn_batch() -> DatafusionDataBatch:
    ctx = df.SessionContext()
    frame = ctx.from_pylist(
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]
    )
    return DatafusionDataBatch(
        frame=frame, context=ctx, source_uri="memory://x"
    )


class TestDatafusionToDataBatch(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_rows_as_dicts(self) -> None:
        with Tapestry() as t:
            batch = emit_dfn_batch(_config=KnotConfig(id="dfn"))
            DatafusionToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.row_count == 3
        # Order may vary depending on engine; check by set of (id, name).
        assert {(row["id"], row["name"]) for row in out.rows} == {
            (1, "a"), (2, "b"), (3, "c"),
        }

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_dfn_batch(_config=KnotConfig(id="dfn"))
            DatafusionToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.source_uri == "memory://x"
