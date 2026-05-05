"""Tests for :class:`IbisFilter`."""

from __future__ import annotations
import unittest

import ibis

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_filter import IbisFilter
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.tapestry import Tapestry



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_does_not_materialise(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "id":     [1, 2, 3, 4],
                "amount": [10.0, 25.0, 5.0, 100.0],
                "region": ["EU", "EU", "EU", "US"],
            },
        )
        duckdb_orders = con
        with Tapestry() as t:
            src = IbisSource(
                connection=duckdb_orders,
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
        # Still a deferred expression — column names accessible without execute.
        assert "amount" in out.column_names
        # Compile + execute manually here to verify the predicate did push down.
        compiled = duckdb_orders.compile(out.expression)
        sql = str(compiled).lower()
        assert "where" in sql
        assert '"region"' in sql or "region" in sql
    
    
    async def test_filter_chains(self) -> None:
        con = ibis.duckdb.connect()
        con.create_table(
            "orders",
            {
                "id":     [1, 2, 3, 4],
                "amount": [10.0, 25.0, 5.0, 100.0],
                "region": ["EU", "EU", "EU", "US"],
            },
        )
        duckdb_orders = con
        with Tapestry() as t:
            src = IbisSource(
                connection=duckdb_orders, table="orders",
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
        rows = duckdb_orders.execute(out.expression)
        assert len(rows) == 2  # EU orders with amount > 5: ids 1, 2
    
    
    def test_construct_rejects_non_callable_predicate(self) -> None:
        @ibis.udf.scalar.python
        def _placeholder(x: int) -> int:
            return x
    
        con = ibis.duckdb.connect()
        con.create_table("t", {"x": [1]})
        with Tapestry():
            src = IbisSource(connection=con, table="t", _config=KnotConfig(id="s"))
            with self.assertRaisesRegex(TypeError, "callable"):
                IbisFilter(
                    batch=src,
                    predicate="region == 'EU'",  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )
