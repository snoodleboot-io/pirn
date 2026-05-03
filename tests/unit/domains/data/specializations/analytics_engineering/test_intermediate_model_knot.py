"""Tests for :class:`IntermediateModelKnot`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.intermediate_model_knot import (
    IntermediateModelKnot,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE stg_orders (order_id INTEGER, customer_id INTEGER)"
    )
    await p.execute(
        "CREATE TABLE stg_customers (customer_id INTEGER, name TEXT)"
    )
    await p.execute(
        "CREATE TABLE int_orders (order_id INTEGER, customer_id INTEGER, name TEXT)"
    )
    await p.execute_many(
        "INSERT INTO stg_orders VALUES (?, ?)", [(1, 10), (2, 11)]
    )
    await p.execute_many(
        "INSERT INTO stg_customers VALUES (?, ?)", [(10, "Alice"), (11, "Bob")]
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_invalid_join_type(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="join_type"):
            IntermediateModelKnot(
                source_pool=pool,
                left_table="stg_orders",
                right_table="stg_customers",
                join_type="CROSS",
                join_condition="stg_orders.customer_id = stg_customers.customer_id",
                select_expression="stg_orders.order_id, stg_orders.customer_id, stg_customers.name",
                target_pool=pool,
                target_table="int_orders",
                _config=KnotConfig(id="int"),
            )

    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            IntermediateModelKnot(
                source_pool="bad",  # type: ignore[arg-type]
                left_table="a",
                right_table="b",
                join_type="INNER",
                join_condition="a.id = b.id",
                select_expression="*",
                target_pool=None,  # type: ignore[arg-type]
                target_table="t",
                _config=KnotConfig(id="int"),
            )

    def test_rejects_invalid_table_identifier(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            IntermediateModelKnot(
                source_pool=pool,
                left_table="stg orders",
                right_table="stg_customers",
                join_type="INNER",
                join_condition="stg_orders.id = stg_customers.id",
                select_expression="*",
                target_pool=pool,
                target_table="int_orders",
                _config=KnotConfig(id="int"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_inner_join_produces_correct_rows(
        self, pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            IntermediateModelKnot(
                source_pool=pool,
                left_table="stg_orders",
                right_table="stg_customers",
                join_type="INNER",
                join_condition=(
                    "stg_orders.customer_id = stg_customers.customer_id"
                ),
                select_expression=(
                    "stg_orders.order_id, stg_orders.customer_id, "
                    "stg_customers.name"
                ),
                target_pool=pool,
                target_table="int_orders",
                _config=KnotConfig(id="int"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await pool.fetch_all(
            "SELECT order_id, customer_id, name FROM int_orders ORDER BY order_id"
        )
        assert rows == [(1, 10, "Alice"), (2, 11, "Bob")]

    async def test_left_join_type_accepted(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            IntermediateModelKnot(
                source_pool=pool,
                left_table="stg_orders",
                right_table="stg_customers",
                join_type="left",
                join_condition=(
                    "stg_orders.customer_id = stg_customers.customer_id"
                ),
                select_expression=(
                    "stg_orders.order_id, stg_orders.customer_id, "
                    "stg_customers.name"
                ),
                target_pool=pool,
                target_table="int_orders",
                _config=KnotConfig(id="int-left"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
