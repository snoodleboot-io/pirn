"""Tests for :class:`PyarrowCast`."""

from __future__ import annotations
import unittest

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_cast import PyarrowCast
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_strings() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table({"id": ["1", "2", "3"], "label": ["a", "b", "c"]})
    )


class TestPyarrowCast(unittest.IsolatedAsyncioTestCase):
    async def test_casts_with_pyarrow_dtype(self) -> None:
        with Tapestry() as t:
            batch = emit_strings(_config=KnotConfig(id="src"))
            PyarrowCast(
                batch=batch,
                casts={"id": pa.int64()},
                _config=KnotConfig(id="cast"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["cast"]
        assert out.table.schema.field("id").type == pa.int64()

    async def test_casts_with_python_primitive(self) -> None:
        with Tapestry() as t:
            batch = emit_strings(_config=KnotConfig(id="src"))
            PyarrowCast(
                batch=batch,
                casts={"id": int},
                _config=KnotConfig(id="cast"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["cast"]
        assert out.table.schema.field("id").type == pa.int64()

    async def test_skips_unknown_columns(self) -> None:
        with Tapestry() as t:
            batch = emit_strings(_config=KnotConfig(id="src"))
            PyarrowCast(
                batch=batch,
                casts={"missing": int},
                _config=KnotConfig(id="cast"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["cast"]
        # Original unaffected.
        assert out.table.schema.field("id").type == pa.string()


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_casts(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                PyarrowCast(
                    batch=batch, casts={},
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_unknown_dtype(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "DataType"):
                PyarrowCast(
                    batch=batch, casts={"id": list},
                    _config=KnotConfig(id="c"),
                )
