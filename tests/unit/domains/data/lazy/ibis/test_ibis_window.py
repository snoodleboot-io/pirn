"""Tests for :class:`IbisWindow`."""

from __future__ import annotations

import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.domains.data.lazy.ibis.ibis_window import IbisWindow
from pirn.tapestry import Tapestry


def _make_orders_con() -> ibis.BaseBackend:
    con = ibis.duckdb.connect()
    con.create_table(
        "orders",
        {
            "region": ["EU", "EU", "EU", "US", "US"],
            "amount": [10.0, 25.0, 5.0,  100.0, 50.0],
        },
    )
    return con


class TestIbisWindow(unittest.IsolatedAsyncioTestCase):
    async def test_window_function_compiles_to_sql_window_clause(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            IbisWindow(
                batch=src,
                windows=lambda table: table.amount.rank()
                    .over(group_by=table.region)
                    .name("rank_in_region"),
                _config=KnotConfig(id="windowed"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["windowed"]
        assert "rank_in_region" in out.column_names
        compiled = str(con.compile(out.expression)).lower()
        assert "over" in compiled

    async def test_multiple_windows(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                _config=KnotConfig(id="src"),
            )
            IbisWindow(
                batch=src,
                windows=lambda table: [
                    table.amount.cumsum().name("running_total"),
                    table.amount.rank().over(group_by=table.region).name("rank_in_region"),
                ],
                _config=KnotConfig(id="windowed"),
            )
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["windowed"]
        assert "running_total" in out.column_names
        assert "rank_in_region" in out.column_names


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_windows_from_upstream_knot(self) -> None:
        con = _make_orders_con()

        @knot
        async def emit_windows() -> object:
            return lambda table: table.amount.cumsum().name("running_total")

        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            win_knot = emit_windows(_config=KnotConfig(id="win"))
            IbisWindow(batch=src, windows=win_knot, _config=KnotConfig(id="windowed"))
        result = await t.run(RunRequest())
        out: IbisTable = result.outputs["windowed"]
        assert "running_total" in out.column_names


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> IbisWindow:
        con = _make_orders_con()
        with Tapestry():
            src = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="src"))
            return IbisWindow(
                batch=src,
                windows=lambda t: t.amount.cumsum().name("x"),
                _config=KnotConfig(id="w"),
                **kwargs,
            )

    async def test_rejects_non_callable_windows(self) -> None:
        con = _make_orders_con()
        batch = IbisTable(expression=con.table("orders"), backend_name="duckdb")
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "callable"):
            await k.process(batch=batch, windows="rank()")
