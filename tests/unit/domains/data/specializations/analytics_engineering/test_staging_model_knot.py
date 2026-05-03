"""Tests for :class:`StagingModelKnot`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.staging_model_knot import (
    StagingModelKnot,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE raw_orders (order_id INTEGER, cust_id INTEGER, amt REAL)"
    )
    await pool.execute_many(
        "INSERT INTO raw_orders VALUES (?, ?, ?)",
        [(1, 10, 99.9), (2, 11, 49.5)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE stg_orders "
        "(order_id INTEGER, customer_id INTEGER, amount REAL, _loaded_at TEXT)"
    )
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool_source(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            StagingModelKnot(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=None,  # type: ignore[arg-type]
                target_table="stg",
                column_map={"a": "b"},
                _config=KnotConfig(id="s"),
            )

    def test_rejects_empty_source_query(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="source_query"):
            StagingModelKnot(
                source_pool=source_pool,
                source_query="",
                target_pool=target_pool,
                target_table="stg_orders",
                column_map={"order_id": "order_id"},
                _config=KnotConfig(id="s"),
            )

    def test_rejects_empty_column_map(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="column_map"):
            StagingModelKnot(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="stg_orders",
                column_map={},
                _config=KnotConfig(id="s"),
            )

    def test_rejects_invalid_target_table(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            StagingModelKnot(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="stg; DROP TABLE x",
                column_map={"a": "b"},
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_writes_rows_with_loaded_at(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            StagingModelKnot(
                source_pool=source_pool,
                source_query="SELECT order_id, cust_id, amt FROM raw_orders",
                target_pool=target_pool,
                target_table="stg_orders",
                column_map={
                    "order_id": "order_id",
                    "cust_id": "customer_id",
                    "amt": "amount",
                },
                _config=KnotConfig(id="staging"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT order_id, customer_id, amount FROM stg_orders ORDER BY order_id"
        )
        assert rows == [(1, 10, 99.9), (2, 11, 49.5)]
        loaded_at_rows = await target_pool.fetch_all(
            "SELECT _loaded_at FROM stg_orders WHERE _loaded_at IS NOT NULL"
        )
        assert len(loaded_at_rows) == 2

    async def test_returns_rows_written_count(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            knot = StagingModelKnot(
                source_pool=source_pool,
                source_query="SELECT order_id, cust_id, amt FROM raw_orders",
                target_pool=target_pool,
                target_table="stg_orders",
                column_map={
                    "order_id": "order_id",
                    "cust_id": "customer_id",
                    "amt": "amount",
                },
                _config=KnotConfig(id="staging"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        output = run_result.outputs[knot.config.id]
        assert output["rows_written"] == 2

    async def test_empty_source_writes_nothing(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        await source_pool.execute("DELETE FROM raw_orders")
        with Tapestry() as t:
            StagingModelKnot(
                source_pool=source_pool,
                source_query="SELECT order_id, cust_id, amt FROM raw_orders",
                target_pool=target_pool,
                target_table="stg_orders",
                column_map={
                    "order_id": "order_id",
                    "cust_id": "customer_id",
                    "amt": "amount",
                },
                _config=KnotConfig(id="staging"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all("SELECT * FROM stg_orders")
        assert rows == []
