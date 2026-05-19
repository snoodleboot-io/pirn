"""Tests for :class:`IbisToTable`."""

from __future__ import annotations

import unittest

try:
    import ibis  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("ibis not installed") from _e

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_connection import IbisConnection
from pirn.domains.data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt
from pirn.domains.data.lazy.ibis.ibis_filter import IbisFilter
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.domains.data.lazy.ibis.ibis_to_table import IbisToTable
from pirn.tapestry import Tapestry


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


class TestIbisToTable(unittest.IsolatedAsyncioTestCase):
    async def test_executes_and_returns_receipt_without_target(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            eu = IbisFilter(
                batch=src,
                predicate=lambda table: table.region == "EU",
                _config=KnotConfig(id="eu"),
            )
            IbisToTable(batch=eu, connection=IbisConnection(con), _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        receipt: IbisExecutionReceipt = result.outputs["exec"]
        assert receipt.backend_name == "duckdb"
        assert receipt.target_table is None
        assert receipt.row_count == 3
        sql = receipt.compiled_sql.lower()
        assert "select" in sql
        assert "where" in sql

    async def test_writes_to_target_table(self) -> None:
        con = _make_orders_con()
        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            eu = IbisFilter(
                batch=src,
                predicate=lambda table: table.region == "EU",
                _config=KnotConfig(id="eu"),
            )
            IbisToTable(
                batch=eu, connection=IbisConnection(con),
                target_table="eu_orders",
                _config=KnotConfig(id="exec"),
            )
        result = await t.run(RunRequest())
        receipt: IbisExecutionReceipt = result.outputs["exec"]
        assert receipt.target_table == "eu_orders"
        assert receipt.row_count == 3
        persisted = con.execute(con.table("eu_orders"))
        assert len(persisted) == 3
        assert set(persisted["region"].tolist()) == {"EU"}


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_target_table_from_upstream_knot(self) -> None:
        con = _make_orders_con()

        @knot
        async def emit_table_name() -> str:
            return "result_table"

        with Tapestry() as t:
            src = IbisSource(
                connection=IbisConnection(con), table="orders",
                backend_name="duckdb", _config=KnotConfig(id="src"),
            )
            name_knot = emit_table_name(_config=KnotConfig(id="name"))
            IbisToTable(
                batch=src, connection=IbisConnection(con),
                target_table=name_knot,
                _config=KnotConfig(id="exec"),
            )
        result = await t.run(RunRequest())
        receipt: IbisExecutionReceipt = result.outputs["exec"]
        assert receipt.target_table == "result_table"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> IbisToTable:
        con = _make_orders_con()
        with Tapestry():
            src = IbisSource(connection=IbisConnection(con), table="orders", _config=KnotConfig(id="src"))
            return IbisToTable(batch=src, connection=IbisConnection(con), _config=KnotConfig(id="x"), **kwargs)

    def _make_batch(self) -> IbisTable:
        con = _make_orders_con()
        return IbisTable(expression=con.table("orders"), backend_name="duckdb")

    async def test_rejects_missing_connection(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "connection is required"):
            await k.process(
                batch=self._make_batch(),
                connection=None,
                target_table=None,
                overwrite=False,
            )

    async def test_rejects_empty_target_table(self) -> None:
        k = self._make_knot()
        con = _make_orders_con()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=self._make_batch(),
                connection=IbisConnection(con),
                target_table="",
                overwrite=False,
            )
