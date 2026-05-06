"""Tests for :class:`PolarsToDataBatch`."""

from __future__ import annotations

import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.bridges.polars_to_data_batch import (
    PolarsToDataBatch,
)
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_polars_batch() -> PolarsDataBatch:
    frame = pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    return PolarsDataBatch(frame=frame, source_uri="memory://x")


class TestPolarsToDataBatch(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_rows_as_dicts(self) -> None:
        with Tapestry() as t:
            batch = emit_polars_batch(_config=KnotConfig(id="polars"))
            PolarsToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.row_count == 3
        assert out.rows == (
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
            {"id": 3, "name": "c"},
        )

    async def test_propagates_metadata(self) -> None:
        with Tapestry() as t:
            batch = emit_polars_batch(_config=KnotConfig(id="polars"))
            PolarsToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.source_uri == "memory://x"
