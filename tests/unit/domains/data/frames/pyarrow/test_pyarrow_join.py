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


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_how(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                PyarrowJoin(
                    left=left,
                    right=right,
                    on="x",
                    how="diagonal",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_both_on_and_left_on(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "not both"):
                PyarrowJoin(
                    left=left,
                    right=right,
                    on="x",
                    left_on="x",
                    right_on="x",
                    _config=KnotConfig(id="j"),
                )

    def test_requires_either_on_or_both_left_right(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            with self.assertRaises(TypeError):
                PyarrowJoin(
                    left=left,
                    right=right,
                    how="inner",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_unsafe_on_column(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "plain identifier"):
                PyarrowJoin(
                    left=left,
                    right=right,
                    on="x; DROP TABLE t",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_mismatched_left_right_lengths(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "same length"):
                PyarrowJoin(
                    left=left,
                    right=right,
                    left_on=("a", "b"),
                    right_on=("c",),
                    _config=KnotConfig(id="j"),
                )

    def test_accepts_valid_inputs(self) -> None:
        with Tapestry():
            left = emit_empty(_config=KnotConfig(id="l"))
            right = emit_empty(_config=KnotConfig(id="r"))
            joined = PyarrowJoin(
                left=left,
                right=right,
                on="x",
                how="left outer",
                _config=KnotConfig(id="j"),
            )
        assert joined.how == "left outer"
