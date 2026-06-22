"""Tests for :class:`IbisFilter`."""

from __future__ import annotations

import unittest

try:
    import ibis
except ImportError as _e:
    raise unittest.SkipTest("ibis not installed") from _e

import ibis
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.ibis.ibis_connection import IbisConnection
from pirn_data.lazy.ibis.ibis_filter import IbisFilter
from pirn_data.lazy.ibis.ibis_source import IbisSource
from pirn_data.lazy.ibis.ibis_table import IbisTable


def _make_orders_con() -> ibis.BaseBackend:
    con = ibis.duckdb.connect()
    con.create_table(
        "orders",
        {
            "id":     [1, 2, 3, 4],
            "amount": [10.0, 25.0, 5.0, 100.0],
            "region": ["EU", "EU", "EU", "US"],
        },
    )
    return con


class TestIbisFilter(unittest.IsolatedAsyncioTestCase):
    async def test_filter_does_not_materialise(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con),
                table="orders",
                backend_name="duckdb",
                _config=KnotConfig(id="src"),
            )
            IbisFilter(
                batch=src,
                predicate=lambda table: table.region == "EU",
                _config=KnotConfig(id="eu"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["eu"]
        assert "amount" in out.column_names
        compiled = con.compile(out.expression)
        sql = str(compiled).lower()
        assert "where" in sql
        assert "region" in sql

    async def test_filter_chains(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            active = IbisFilter(
                batch=src,
                predicate=lambda table: table.region == "EU",
                _config=KnotConfig(id="eu"),
            )
            IbisFilter(
                batch=active,
                predicate=lambda table: table.amount > 5.0,
                _config=KnotConfig(id="big_eu"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["big_eu"]
        rows = con.execute(out.expression)
        assert len(rows) == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        con = _make_orders_con()

        @knot
        async def emit_predicate() -> object:
            return lambda table: table.region == "EU"

        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            pred_knot = emit_predicate(_config=KnotConfig(id="pred"))
            IbisFilter(batch=src, predicate=pred_knot, _config=KnotConfig(id="eu"))
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["eu"]
        rows = con.execute(out.expression)
        assert len(rows) == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> IbisFilter:
        con = _make_orders_con()
        with Tapestry():
            src = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="src"))
            return IbisFilter(batch=src, _config=KnotConfig(id="f"), **kwargs)

    async def test_rejects_non_callable_predicate(self) -> None:
        con = _make_orders_con()
        expr = con.table("orders")
        batch = IbisTable(expression=expr, backend_name="duckdb")
        k = self._make_knot(predicate=lambda t: t.region == "EU")
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(batch=batch, predicate="region == 'EU'")
