"""Tests for :class:`DuckdbJoin`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.frames.duckdb.duckdb_join import DuckdbJoin
from pirn.tapestry import Tapestry


def _make_users(connection: duckdb.DuckDBPyConnection) -> DuckdbDataBatch:
    connection.execute(
        "CREATE TABLE users AS "
        "SELECT * FROM (VALUES (1, 'alice'), (2, 'bob'), (3, 'carol')) "
        "AS v(user_id, name)"
    )
    return DuckdbDataBatch(
        relation=connection.table("users"), connection=connection
    )


def _make_orders(connection: duckdb.DuckDBPyConnection) -> DuckdbDataBatch:
    connection.execute(
        "CREATE TABLE orders AS "
        "SELECT * FROM (VALUES "
        "(1, 10.0), (1, 20.0), (2, 30.0), (4, 40.0)"
        ") AS v(user_id, amount)"
    )
    return DuckdbDataBatch(
        relation=connection.table("orders"), connection=connection
    )


@knot
async def emit_users_alone() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    return _make_users(connection)


@knot
async def emit_orders_alone() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    return _make_orders(connection)


class TestDuckdbJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_key(self) -> None:
        with Tapestry() as t:
            users = emit_users_alone(_config=KnotConfig(id="users"))
            orders = emit_orders_alone(_config=KnotConfig(id="orders"))
            DuckdbJoin(
                left=users, right=orders, on="user_id", how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["joined"]
        rows = out.relation.fetchall()
        # alice (2 orders) + bob (1) → 3 matched rows.
        assert len(rows) == 3

    async def test_left_join_keeps_unmatched_left_rows(self) -> None:
        with Tapestry() as t:
            users = emit_users_alone(_config=KnotConfig(id="users"))
            orders = emit_orders_alone(_config=KnotConfig(id="orders"))
            DuckdbJoin(
                left=users, right=orders, on="user_id", how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["joined"]
        rows = out.relation.fetchall()
        names = {row[1] for row in rows}
        # carol has no orders but appears in the left-join result.
        assert "carol" in names

    async def test_join_with_explicit_condition(self) -> None:
        @knot
        async def emit_renamed() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            connection.execute(
                "CREATE TABLE u AS "
                "SELECT * FROM (VALUES (1, 'alice'), (2, 'bob')) AS v(uid, name)"
            )
            return DuckdbDataBatch(
                relation=connection.table("u"), connection=connection
            )

        @knot
        async def emit_orders_renamed() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            connection.execute(
                "CREATE TABLE o AS "
                "SELECT * FROM (VALUES (1, 10.0), (2, 20.0)) AS v(customer_id, amount)"
            )
            return DuckdbDataBatch(
                relation=connection.table("o"), connection=connection
            )

        with Tapestry() as t:
            left = emit_renamed(_config=KnotConfig(id="users"))
            right = emit_orders_renamed(_config=KnotConfig(id="orders"))
            DuckdbJoin(
                left=left, right=right,
                condition="uid = customer_id",
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["joined"]
        rows = out.relation.fetchall()
        assert len(rows) == 2

    async def test_cross_join(self) -> None:
        @knot
        async def emit_left() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            connection.execute(
                "CREATE TABLE l AS SELECT * FROM (VALUES (1), (2)) AS v(x)"
            )
            return DuckdbDataBatch(
                relation=connection.table("l"), connection=connection
            )

        @knot
        async def emit_right() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            connection.execute(
                "CREATE TABLE r AS SELECT * FROM (VALUES ('a'), ('b'), ('c')) AS v(y)"
            )
            return DuckdbDataBatch(
                relation=connection.table("r"), connection=connection
            )

        with Tapestry() as t:
            left = emit_left(_config=KnotConfig(id="left"))
            right = emit_right(_config=KnotConfig(id="right"))
            DuckdbJoin(
                left=left, right=right, how="cross",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["joined"]
        rows = out.relation.fetchall()
        assert len(rows) == 6  # 2 × 3


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_how(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                DuckdbJoin(
                    left=left, right=right, on="x", how="diagonal",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_both_on_and_condition(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "not both"):
                DuckdbJoin(
                    left=left, right=right,
                    on="x", condition="x = x",
                    _config=KnotConfig(id="j"),
                )

    def test_requires_on_or_condition_for_non_cross(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "provide on="):
                DuckdbJoin(
                    left=left, right=right, how="inner",
                    _config=KnotConfig(id="j"),
                )

    def test_cross_join_rejects_keys(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(TypeError, "cross join takes no"):
                DuckdbJoin(
                    left=left, right=right, how="cross", on="x",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_unsafe_on_column(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "plain identifier"):
                DuckdbJoin(
                    left=left, right=right,
                    on="x; DROP TABLE t",
                    _config=KnotConfig(id="j"),
                )

    def test_rejects_injection_in_condition(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            left = empty(_config=KnotConfig(id="l"))
            right = empty(_config=KnotConfig(id="r"))
            with self.assertRaisesRegex(ValueError, "forbidden"):
                DuckdbJoin(
                    left=left, right=right,
                    condition="a = b; DROP TABLE t",
                    _config=KnotConfig(id="j"),
                )
