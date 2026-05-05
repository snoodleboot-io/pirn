"""Tests for :class:`PyarrowJoin`."""

from __future__ import annotations

import unittest

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_join import PyarrowJoin
from pirn.tapestry import Tapestry


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({"x": pa.array([], type=pa.int64())}))


@knot
async def emit_users() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "user_id": [1, 2, 3],
                "name":    ["alice", "bob", "carol"],
            }
        )
    )


@knot
async def emit_orders() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "user_id": [1, 1, 2, 4],
                "amount":  [10.0, 20.0, 30.0, 40.0],
            }
        )
    )


@knot
async def emit_empty() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({"x": pa.array([], type=pa.int64())}))


class TestPyarrowJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        with Tapestry() as t:
            users = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PyarrowJoin(
                left=users,
                right=orders,
                on="user_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["joined"]
        # Inner join: alice (2 orders) + bob (1) = 3 rows; carol drops out.
        assert out.row_count == 3
        cols = set(out.table.column_names)
        # Union of left + right columns (key coalesced by default).
        assert {"user_id", "name", "amount"}.issubset(cols)

    async def test_left_outer_keeps_unmatched_left_rows(self) -> None:
        with Tapestry() as t:
            users = emit_users(_config=KnotConfig(id="users"))
            orders = emit_orders(_config=KnotConfig(id="orders"))
            PyarrowJoin(
                left=users,
                right=orders,
                on="user_id",
                how="left outer",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["joined"]
        names = set(out.table.column("name").to_pylist())
        # carol has no orders but appears in the left-outer result.
        assert "carol" in names

    async def test_join_with_left_on_right_on(self) -> None:
        @knot
        async def emit_renamed_users() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table({"uid": [1, 2], "name": ["alice", "bob"]})
            )

        @knot
        async def emit_renamed_orders() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table(
                    {"customer_id": [1, 2], "amount": [10.0, 20.0]}
                )
            )

        with Tapestry() as t:
            left = emit_renamed_users(_config=KnotConfig(id="users"))
            right = emit_renamed_orders(_config=KnotConfig(id="orders"))
            PyarrowJoin(
                left=left,
                right=right,
                left_on="uid",
                right_on="customer_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["joined"]
        assert out.row_count == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowJoin:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            return PyarrowJoin(
                left=left, right=right, _config=KnotConfig(id="j"), **kwargs
            )

    async def test_rejects_unknown_how(self) -> None:
        k = self._make_knot(on="x", how="diagonal")
        with self.assertRaisesRegex(ValueError, "how must be one of"):
            await k.process(
                left=_empty_batch(), right=_empty_batch(),
                on="x", left_on=None, right_on=None, how="diagonal",
            )

    async def test_rejects_both_on_and_left_on(self) -> None:
        k = self._make_knot(on="x", left_on="x", right_on="x")
        with self.assertRaisesRegex(TypeError, "not both"):
            await k.process(
                left=_empty_batch(), right=_empty_batch(),
                on="x", left_on="x", right_on="x", how="inner",
            )

    async def test_requires_either_on_or_both_left_right(self) -> None:
        k = self._make_knot(how="inner")
        with self.assertRaises(TypeError):
            await k.process(
                left=_empty_batch(), right=_empty_batch(),
                on=None, left_on=None, right_on=None, how="inner",
            )

    async def test_rejects_unsafe_on_column(self) -> None:
        k = self._make_knot(on="x; DROP TABLE t")
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(
                left=_empty_batch(), right=_empty_batch(),
                on="x; DROP TABLE t", left_on=None, right_on=None, how="inner",
            )

    async def test_rejects_mismatched_left_right_lengths(self) -> None:
        k = self._make_knot(left_on=("a", "b"), right_on=("c",))
        with self.assertRaisesRegex(ValueError, "same length"):
            await k.process(
                left=_empty_batch(), right=_empty_batch(),
                on=None, left_on=("a", "b"), right_on=("c",), how="inner",
            )
