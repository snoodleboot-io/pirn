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


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({}))


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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_casts_from_upstream_knot(self) -> None:
        @knot
        async def emit_casts() -> dict:
            return {"id": int}

        with Tapestry() as t:
            batch = emit_strings(_config=KnotConfig(id="src"))
            casts_knot = emit_casts(_config=KnotConfig(id="casts"))
            PyarrowCast(
                batch=batch,
                casts=casts_knot,
                _config=KnotConfig(id="cast"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["cast"]
        assert out.table.schema.field("id").type == pa.int64()


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowCast:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PyarrowCast(
                batch=batch, _config=KnotConfig(id="c"), **kwargs
            )

    async def test_rejects_empty_casts(self) -> None:
        k = self._make_knot(casts={})
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_empty_batch(), casts={})

    async def test_rejects_unknown_dtype(self) -> None:
        k = self._make_knot(casts={"id": list})
        with self.assertRaisesRegex(TypeError, "DataType"):
            await k.process(batch=_empty_batch(), casts={"id": list})
