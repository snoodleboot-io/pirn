"""Tests for :class:`PyarrowFilter`."""

from __future__ import annotations
import unittest

import pyarrow as pa
import pyarrow.compute as pc

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_filter import PyarrowFilter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "id":     [1, 2, 3, 4],
                "active": [True, False, True, False],
                "region": ["EU", "US", "US", "EU"],
            }
        )
    )


class TestPyarrowFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_rows_matching_expression(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PyarrowFilter(
                batch=batch,
                expression=pc.field("active"),
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["active"]
        assert out.table.column("id").to_pylist() == [1, 3]

    async def test_predicate_callable(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            PyarrowFilter(
                batch=batch,
                predicate=lambda table: pc.equal(
                    table.column("region"), "EU"
                ),
                _config=KnotConfig(id="eu"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["eu"]
        assert sorted(out.table.column("id").to_pylist()) == [1, 4]


class TestConstruction(unittest.TestCase):
    def test_rejects_neither_expression_nor_predicate(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "provide either"):
                PyarrowFilter(
                    batch=batch,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_both_expression_and_predicate(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "not both"):
                PyarrowFilter(
                    batch=batch,
                    expression=pc.field("a"),
                    predicate=lambda t: True,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_expression(self) -> None:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "Expression"):
                PyarrowFilter(
                    batch=batch,
                    expression="a > 1",  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )
