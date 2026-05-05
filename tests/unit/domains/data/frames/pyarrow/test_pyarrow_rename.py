"""Tests for :class:`PyarrowRename`."""

from __future__ import annotations
import unittest

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_rename import PyarrowRename
from pirn.tapestry import Tapestry


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


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_mapping(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                PyarrowRename(
                    batch=batch, mapping={},
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_non_string_keys(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty strings"):
                PyarrowRename(
                    batch=batch,
                    mapping={"": "x"},
                    _config=KnotConfig(id="r"),
                )
