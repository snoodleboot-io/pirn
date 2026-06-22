"""Tests for :class:`PyarrowFilter`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

import pyarrow as pa
import pyarrow.compute as pc
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn_data.frames.pyarrow.pyarrow_filter import PyarrowFilter


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({}))


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


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_expression_from_upstream_knot(self) -> None:
        @knot
        async def emit_expression() -> object:
            return pc.field("active")

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            expr_knot = emit_expression(_config=KnotConfig(id="expr"))
            PyarrowFilter(
                batch=batch,
                expression=expr_knot,
                _config=KnotConfig(id="filtered"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["filtered"]
        assert out.table.column("id").to_pylist() == [1, 3]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowFilter:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PyarrowFilter(
                batch=batch, _config=KnotConfig(id="f"), **kwargs
            )

    async def test_rejects_neither_expression_nor_predicate(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "provide either"):
            await k.process(
                batch=_empty_batch(), expression=None, predicate=None
            )

    async def test_rejects_both_expression_and_predicate(self) -> None:
        k = self._make_knot(expression=pc.field("a"), predicate=lambda t: True)
        with self.assertRaisesRegex(TypeError, "not both"):
            await k.process(
                batch=_empty_batch(),
                expression=pc.field("a"),
                predicate=lambda t: True,
            )

    async def test_rejects_non_expression(self) -> None:
        k = self._make_knot(expression="a > 1")
        with self.assertRaisesRegex(TypeError, "Expression"):
            await k.process(
                batch=_empty_batch(),
                expression="a > 1",
                predicate=None,
            )
