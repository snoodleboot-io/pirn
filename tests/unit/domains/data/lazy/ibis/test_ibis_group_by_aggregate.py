"""Tests for :class:`IbisGroupByAggregate`."""

from __future__ import annotations
import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_group_by_aggregate import IbisGroupByAggregate
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_aggregation(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            },
        )
        duckdb_orders = con
        with Tapestry() as t:
            src = IbisSource(
                connection=duckdb_orders, table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            IbisGroupByAggregate(
                batch=src,
                by=("region",),
                aggregations=lambda table: table.amount.sum().name("total"),
                _config=KnotConfig(id="totals"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["totals"]
        rows = duckdb_orders.execute(out.expression).set_index("region")
        assert rows.loc["EU", "total"] == 40.0
        assert rows.loc["US", "total"] == 150.0
    
    
    async def test_multiple_aggregations(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            },
        )
        duckdb_orders = con
        with Tapestry() as t:
            src = IbisSource(
                connection=duckdb_orders, table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            IbisGroupByAggregate(
                batch=src,
                by=("region",),
                aggregations=lambda table: [
                    table.amount.sum().name("total"),
                    table.customer.nunique().name("n_customers"),
                ],
                _config=KnotConfig(id="metrics"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["metrics"]
        rows = duckdb_orders.execute(out.expression).set_index("region")
        assert rows.loc["EU", "total"] == 40.0
        assert rows.loc["EU", "n_customers"] == 2
        assert rows.loc["US", "n_customers"] == 1
    
    
    async def test_composite_group_by(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            },
        )
        duckdb_orders = con
        with Tapestry() as t:
            src = IbisSource(
                connection=duckdb_orders, table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            IbisGroupByAggregate(
                batch=src,
                by=("region", "customer"),
                aggregations=lambda table: table.amount.sum().name("total"),
                _config=KnotConfig(id="totals"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["totals"]
        rows = duckdb_orders.execute(out.expression)
        assert len(rows) == 3  # (EU, alice), (EU, bob), (US, carol)
    
    
    def test_construct_rejects_string_by(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            },
        )
        duckdb_orders = con
        with Tapestry():
            src = IbisSource(
                connection=duckdb_orders, table="orders",
                _config=KnotConfig(id="src"),
            )
            with self.assertRaisesRegex(TypeError, "sequence"):
                IbisGroupByAggregate(
                    batch=src,
                    by="region",  # type: ignore[arg-type]
                    aggregations=lambda t: t.amount.sum().name("x"),
                    _config=KnotConfig(id="g"),
                )
    
    
    def test_construct_rejects_empty_by(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "region":   ["EU", "EU", "EU", "US", "US"],
                "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
                "customer": ["alice", "bob", "alice", "carol", "carol"],
            },
        )
        duckdb_orders = con
        with Tapestry():
            src = IbisSource(
                connection=duckdb_orders, table="orders",
                _config=KnotConfig(id="src"),
            )
            with self.assertRaisesRegex(ValueError, "non-empty"):
                IbisGroupByAggregate(
                    batch=src, by=(),
                    aggregations=lambda t: t.amount.sum().name("x"),
                    _config=KnotConfig(id="g"),
                )
