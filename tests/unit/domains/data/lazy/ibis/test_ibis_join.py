"""Tests for :class:`IbisJoin`."""

from __future__ import annotations

import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_join import IbisJoin
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry


def _make_con() -> ibis.BaseBackend:
    con = ibis.duckdb.connect()
    con.create_table(
        "users",
        {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
    )
    con.create_table(
        "orders",
        {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
    )
    return con


class TestIbisJoin(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_column(self) -> None:
        con = _make_con()
        with Tapestry() as t:
            users = IbisSource(connection=IbisConnection(con), table="users", _config=KnotConfig(id="users"))
            orders = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="orders"))
            IbisJoin(
                left=users, right=orders,
                predicates=("user_id",), how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = con.execute(out.expression)
        assert len(rows) == 3

    async def test_left_join_keeps_unmatched(self) -> None:
        con = _make_con()
        with Tapestry() as t:
            users = IbisSource(connection=IbisConnection(con), table="users", _config=KnotConfig(id="users"))
            orders = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="orders"))
            IbisJoin(
                left=users, right=orders,
                predicates=("user_id",), how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = con.execute(out.expression)
        assert "carol" in rows["name"].tolist()

    async def test_predicate_callable(self) -> None:
        con = _make_con()
        with Tapestry() as t:
            users = IbisSource(connection=IbisConnection(con), table="users", _config=KnotConfig(id="users"))
            orders = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="orders"))
            IbisJoin(
                left=users, right=orders,
                predicates=lambda left, right: left.user_id == right.user_id,
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = con.execute(out.expression)
        assert len(rows) == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_how_from_upstream_knot(self) -> None:
        con = _make_con()

        @knot
        async def emit_how() -> str:
            return "inner"

        with Tapestry() as t:
            users = IbisSource(connection=IbisConnection(con), table="users", _config=KnotConfig(id="users"))
            orders = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="orders"))
            how_knot = emit_how(_config=KnotConfig(id="how"))
            IbisJoin(
                left=users, right=orders,
                predicates=("user_id",), how=how_knot,
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = con.execute(out.expression)
        assert len(rows) == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> IbisJoin:
        con = _make_con()
        with Tapestry():
            u = IbisSource(connection=IbisConnection(con), table="users", _config=KnotConfig(id="u"))
            o = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="o"))
            return IbisJoin(
                left=u, right=o,
                predicates=("user_id",),
                _config=KnotConfig(id="j"),
                **kwargs,
            )

    def _make_tables(self) -> tuple[IbisTable, IbisTable]:
        con = _make_con()
        return (
            IbisTable(expression=con.table("users"), backend_name="duckdb"),
            IbisTable(expression=con.table("orders"), backend_name="duckdb"),
        )

    async def test_rejects_unknown_how(self) -> None:
        left, right = self._make_tables()
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "how must be one of"):
            await k.process(left=left, right=right, predicates=("user_id",), how="diagonal")

    async def test_rejects_predicates_for_cross(self) -> None:
        left, right = self._make_tables()
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "cross join takes no"):
            await k.process(left=left, right=right, predicates=("user_id",), how="cross")

    async def test_requires_predicates_for_non_cross(self) -> None:
        left, right = self._make_tables()
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "predicates is required"):
            await k.process(left=left, right=right, predicates=None, how="inner")
