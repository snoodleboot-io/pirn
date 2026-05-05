"""Tests for :class:`IbisJoin`."""

from __future__ import annotations
import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_join import IbisJoin
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_inner_join_on_shared_column(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry() as t:
            users = IbisSource(
                connection=duckdb_users_orders, table="users",
                _config=KnotConfig(id="users"),
            )
            orders = IbisSource(
                connection=duckdb_users_orders, table="orders",
                _config=KnotConfig(id="orders"),
            )
            IbisJoin(
                left=users, right=orders,
                predicates=("user_id",), how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = duckdb_users_orders.execute(out.expression)
        assert len(rows) == 3   # alice has 2 orders, bob has 1, carol has 0
    
    
    async def test_left_join_keeps_unmatched(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry() as t:
            users = IbisSource(
                connection=duckdb_users_orders, table="users",
                _config=KnotConfig(id="users"),
            )
            orders = IbisSource(
                connection=duckdb_users_orders, table="orders",
                _config=KnotConfig(id="orders"),
            )
            IbisJoin(
                left=users, right=orders,
                predicates=("user_id",), how="left",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = duckdb_users_orders.execute(out.expression)
        assert "carol" in rows["name"].tolist()
    
    
    async def test_predicate_callable(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry() as t:
            users = IbisSource(
                connection=duckdb_users_orders, table="users",
                _config=KnotConfig(id="users"),
            )
            orders = IbisSource(
                connection=duckdb_users_orders, table="orders",
                _config=KnotConfig(id="orders"),
            )
            IbisJoin(
                left=users, right=orders,
                predicates=lambda left, right: left.user_id == right.user_id,
                how="inner",
                _config=KnotConfig(id="joined"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["joined"]
        rows = duckdb_users_orders.execute(out.expression)
        assert len(rows) == 3
    
    
    def test_construct_rejects_unknown_how(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry():
            u = IbisSource(connection=duckdb_users_orders, table="users", _config=KnotConfig(id="u"))
            o = IbisSource(connection=duckdb_users_orders, table="orders", _config=KnotConfig(id="o"))
            with self.assertRaisesRegex(ValueError, "how must be one of"):
                IbisJoin(
                    left=u, right=o,
                    predicates=("user_id",), how="diagonal",
                    _config=KnotConfig(id="j"),
                )
    
    
    def test_construct_rejects_predicates_for_cross(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry():
            u = IbisSource(connection=duckdb_users_orders, table="users", _config=KnotConfig(id="u"))
            o = IbisSource(connection=duckdb_users_orders, table="orders", _config=KnotConfig(id="o"))
            with self.assertRaisesRegex(TypeError, "cross join takes no"):
                IbisJoin(
                    left=u, right=o,
                    predicates=("user_id",), how="cross",
                    _config=KnotConfig(id="j"),
                )
    
    
    def test_construct_requires_predicates_for_non_cross(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "users",
            {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]},
        )
        con.create_table(
            "orders",
            {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]},
        )
        duckdb_users_orders = con
        with Tapestry():
            u = IbisSource(connection=duckdb_users_orders, table="users", _config=KnotConfig(id="u"))
            o = IbisSource(connection=duckdb_users_orders, table="orders", _config=KnotConfig(id="o"))
            with self.assertRaisesRegex(TypeError, "predicates is required"):
                IbisJoin(
                    left=u, right=o,
                    how="inner",
                    _config=KnotConfig(id="j"),
                )
