"""Tests for :class:`PyarrowDeduplicate`."""

from __future__ import annotations
import unittest

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_deduplicate import (
    PyarrowDeduplicate,
)
from pirn.tapestry import Tapestry


@knot
async def emit_dupes() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "id":   [1, 1, 2, 2, 3],
                "name": ["a", "a2", "b", "b2", "c"],
            }
        )
    )


class TestPyarrowDeduplicate(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_first_occurrence(self) -> None:
        with Tapestry() as t:
            batch = emit_dupes(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch,
                keys=("id",),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        ids = out.table.column("id").to_pylist()
        names = out.table.column("name").to_pylist()
        assert ids == [1, 2, 3]
        assert names == ["a", "b", "c"]

    async def test_composite_keys(self) -> None:
        @knot
        async def emit_two_keys() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table(
                    {
                        "region": ["EU", "EU", "US", "EU"],
                        "tier":   ["A",  "A",  "A",  "B"],
                        "rev":    [1,    2,    3,    4],
                    }
                )
            )

        with Tapestry() as t:
            batch = emit_two_keys(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch,
                keys=("region", "tier"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        # 3 unique (region, tier) tuples; first-occurrence rev values are 1,3,4.
        assert sorted(out.table.column("rev").to_pylist()) == [1, 3, 4]

    async def test_empty_table_passes_through(self) -> None:
        @knot
        async def emit_empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table({"id": pa.array([], type=pa.int64())})
            )

        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch, keys=("id",),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        assert out.row_count == 0


class TestConstruction(unittest.TestCase):
    def test_rejects_string_keys(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "sequence"):
                PyarrowDeduplicate(
                    batch=batch,
                    keys="id",  # type: ignore[arg-type]
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_empty_keys(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                PyarrowDeduplicate(
                    batch=batch, keys=(),
                    _config=KnotConfig(id="d"),
                )
