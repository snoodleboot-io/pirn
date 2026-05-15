"""Tests for :class:`PyarrowRename`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_rename import PyarrowRename
from pirn.tapestry import Tapestry


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({}))


@knot
async def emit_users() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table({"id": [1, 2], "name": ["a", "b"]})
    )


class TestPyarrowRename(unittest.IsolatedAsyncioTestCase):
    async def test_renames_column(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PyarrowRename(
                batch=batch,
                mapping={"name": "username"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["renamed"]
        assert out.column_names == ("id", "username")

    async def test_skips_unknown_columns(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PyarrowRename(
                batch=batch,
                mapping={"missing": "ghost", "name": "n"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["renamed"]
        assert out.column_names == ("id", "n")


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_mapping_from_upstream_knot(self) -> None:
        @knot
        async def emit_mapping() -> dict:
            return {"name": "username"}

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            mapping_knot = emit_mapping(_config=KnotConfig(id="mapping"))
            PyarrowRename(
                batch=batch,
                mapping=mapping_knot,
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["renamed"]
        assert out.column_names == ("id", "username")


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowRename:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PyarrowRename(
                batch=batch, _config=KnotConfig(id="r"), **kwargs
            )

    async def test_rejects_empty_mapping(self) -> None:
        k = self._make_knot(mapping={})
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_empty_batch(), mapping={})

    async def test_rejects_non_string_keys(self) -> None:
        k = self._make_knot(mapping={"": "x"})
        with self.assertRaisesRegex(TypeError, "non-empty strings"):
            await k.process(batch=_empty_batch(), mapping={"": "x"})
