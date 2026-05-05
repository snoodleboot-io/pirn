"""Tests for :class:`IbisGroupByAggregate`."""

from __future__ import annotations

import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_group_by_aggregate import IbisGroupByAggregate
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry


def _make_orders_con() -> ibis.BaseBackend:
    con = ibis.duckdb.connect()
    con.create_table(
        "orders",
        {
            "region":   ["EU", "EU", "EU", "US", "US"],
            "amount":   [10.0, 25.0, 5.0,  100.0, 50.0],
            "customer": ["alice", "bob", "alice", "carol", "carol"],
        },
    )
    return con


class TestIbisGroupByAggregate(unittest.IsolatedAsyncioTestCase):
    async def test_single_aggregation(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=con, table="orders",
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
        rows = con.execute(out.expression).set_index("region")
        assert rows.loc["EU", "total"] == 40.0
        assert rows.loc["US", "total"] == 150.0

    async def test_multiple_aggregations(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=con, table="orders",
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
        rows = con.execute(out.expression).set_index("region")
        assert rows.loc["EU", "total"] == 40.0
        assert rows.loc["EU", "n_customers"] == 2
        assert rows.loc["US", "n_customers"] == 1

    async def test_composite_group_by(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=con, table="orders",
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
        rows = con.execute(out.expression)
        assert len(rows) == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_by_from_upstream_knot(self) -> None:
        con = _make_orders_con()

        @knot
        async def emit_by() -> tuple:
            return ("region",)

        with Tapestry() as t:
            src = IbisSource(
                connection=con, table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            by_knot = emit_by(_config=KnotConfig(id="by"))
            IbisGroupByAggregate(
                batch=src,
                by=by_knot,
                aggregations=lambda table: table.amount.sum().name("total"),
                _config=KnotConfig(id="totals"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["totals"]
        rows = con.execute(out.expression)
        assert "region" in rows.columns


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> IbisGroupByAggregate:
        con = _make_orders_con()
        with Tapestry():
            src = IbisSource(connection=con, table="orders", _config=KnotConfig(id="src"))
            return IbisGroupByAggregate(
                batch=src,
                by=("region",),
                aggregations=lambda t: t.amount.sum().name("x"),
                _config=KnotConfig(id="g"),
                **kwargs,
            )

    async def test_rejects_string_by(self) -> None:
        con = _make_orders_con()
        expr = con.table("orders")
        batch = IbisTable(expression=expr, backend_name="duckdb")
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(
                batch=batch,
                by="region",
                aggregations=lambda t: t.amount.sum().name("x"),
            )

    async def test_rejects_empty_by(self) -> None:
        con = _make_orders_con()
        expr = con.table("orders")
        batch = IbisTable(expression=expr, backend_name="duckdb")
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=batch,
                by=(),
                aggregations=lambda t: t.amount.sum().name("x"),
            )

    async def test_rejects_non_callable_aggregations(self) -> None:
        con = _make_orders_con()
        expr = con.table("orders")
        batch = IbisTable(expression=expr, backend_name="duckdb")
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(
                batch=batch,
                by=("region",),
                aggregations="sum",
            )
