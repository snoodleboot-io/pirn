"""Tests for :class:`IbisToTable`."""

from __future__ import annotations

import ibis
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt
from pirn.domains.data.lazy.ibis.ibis_filter import IbisFilter
from pirn.domains.data.lazy.ibis.ibis_source import IbisSource
from pirn.domains.data.lazy.ibis.ibis_to_table import IbisToTable
from pirn.tapestry import Tapestry


@pytest.fixture
def duckdb_orders():
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


@pytest.mark.asyncio
async def test_executes_and_returns_receipt_without_target(duckdb_orders) -> None:
    with Tapestry() as t:
        src = IbisSource(
            connection=duckdb_orders, table="orders",
            backend_name="duckdb", _config=KnotConfig(id="src"),
        )
        eu = IbisFilter(
            batch=src,
            predicate=lambda table: table.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        IbisToTable(
            batch=eu,
            connection=duckdb_orders,
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    receipt: IbisExecutionReceipt = result.outputs["exec"]
    assert receipt.backend_name == "duckdb"
    assert receipt.target_table is None
    assert receipt.row_count == 3   # 3 EU orders
    sql = receipt.compiled_sql.lower()
    assert "select" in sql
    assert "where" in sql


@pytest.mark.asyncio
async def test_writes_to_target_table(duckdb_orders) -> None:
    with Tapestry() as t:
        src = IbisSource(
            connection=duckdb_orders, table="orders",
            backend_name="duckdb", _config=KnotConfig(id="src"),
        )
        eu = IbisFilter(
            batch=src,
            predicate=lambda table: table.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        IbisToTable(
            batch=eu,
            connection=duckdb_orders,
            target_table="eu_orders",
            _config=KnotConfig(id="exec"),
        )
    result = await t.run(RunRequest())
    receipt: IbisExecutionReceipt = result.outputs["exec"]
    assert receipt.target_table == "eu_orders"
    assert receipt.row_count == 3

    persisted = duckdb_orders.execute(duckdb_orders.table("eu_orders"))
    assert len(persisted) == 3
    assert set(persisted["region"].tolist()) == {"EU"}


def test_construct_rejects_missing_connection(duckdb_orders) -> None:
    with Tapestry():
        src = IbisSource(connection=duckdb_orders, table="orders", _config=KnotConfig(id="src"))
        with pytest.raises(TypeError, match="connection is required"):
            IbisToTable(
                batch=src, connection=None,
                _config=KnotConfig(id="x"),
            )


def test_construct_rejects_empty_target_table(duckdb_orders) -> None:
    with Tapestry():
        src = IbisSource(connection=duckdb_orders, table="orders", _config=KnotConfig(id="src"))
        with pytest.raises(ValueError, match="non-empty"):
            IbisToTable(
                batch=src, connection=duckdb_orders, target_table="",
                _config=KnotConfig(id="x"),
            )
