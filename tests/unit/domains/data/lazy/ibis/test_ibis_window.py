"""Tests for :class:`IbisWindow`."""

from __future__ import annotations

import ibis
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable
from pirn.domains.data.lazy.ibis.ibis_window import IbisWindow
from pirn.tapestry import Tapestry


@pytest.fixture
def duckdb_orders():
    con = ibis.duckdb.connect()
    con.create_table(
        "orders",
        {
            "region": ["EU", "EU", "EU", "US", "US"],
            "amount": [10.0, 25.0, 5.0,  100.0, 50.0],
        },
    )
    return con


@pytest.mark.asyncio
async def test_window_function_compiles_to_sql_window_clause(duckdb_orders) -> None:
    with Tapestry() as t:
        src = IbisSource(
            connection=duckdb_orders, table="orders",
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

    compiled = str(duckdb_orders.compile(out.expression)).lower()
    # The push-down test for IbisWindow: the SQL contains a window clause.
    assert "over" in compiled


@pytest.mark.asyncio
async def test_multiple_windows(duckdb_orders) -> None:
    with Tapestry() as t:
        src = IbisSource(
            connection=duckdb_orders, table="orders",
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


def test_construct_rejects_non_callable(duckdb_orders) -> None:
    with Tapestry():
        src = IbisSource(connection=duckdb_orders, table="orders", _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="callable"):
            IbisWindow(
                batch=src,
                windows="rank()",  # type: ignore[arg-type]
                _config=KnotConfig(id="w"),
            )
