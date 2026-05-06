"""Tests for :class:`PyarrowToDataBatch`."""

from __future__ import annotations

import unittest

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pyarrow.bridges.pyarrow_to_data_batch import (
    PyarrowToDataBatch,
)
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_pyarrow_batch() -> PyarrowDataBatch:
    table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    return PyarrowDataBatch(table=table, source_uri="memory://x")


class TestPyarrowToDataBatch(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_rows_as_dicts(self) -> None:
        with Tapestry() as t:
            batch = emit_pyarrow_batch(_config=KnotConfig(id="arrow"))
            PyarrowToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
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
            batch = emit_pyarrow_batch(_config=KnotConfig(id="arrow"))
            PyarrowToDataBatch(batch=batch, _config=KnotConfig(id="dict"))
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["dict"]
        assert out.source_uri == "memory://x"
