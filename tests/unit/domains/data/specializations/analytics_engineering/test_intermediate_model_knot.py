"""Tests for :class:`IntermediateModelKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.intermediate_model_knot import (
    IntermediateModelKnot,
)
from pirn.tapestry import Tapestry

_LEFT_TABLE = "stg_orders"
_RIGHT_TABLE = "stg_customers"
_JOIN_TYPE = "INNER"
_JOIN_CONDITION = "stg_orders.customer_id = stg_customers.customer_id"
_SELECT_EXPRESSION = "stg_orders.order_id, stg_orders.customer_id, stg_customers.name"
_TARGET_TABLE = "int_orders"


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE stg_orders (order_id INTEGER, customer_id INTEGER)")
    await p.execute("CREATE TABLE stg_customers (customer_id INTEGER, name TEXT)")
    await p.execute(
        "CREATE TABLE int_orders (order_id INTEGER, customer_id INTEGER, name TEXT)"
    )
    await p.execute_many(
        "INSERT INTO stg_orders VALUES (?, ?)", [(1, 10), (2, 11)]
    )
    await p.execute_many(
        "INSERT INTO stg_customers VALUES (?, ?)", [(10, "Alice"), (11, "Bob")]
    )
    return p


def _make_knot(pool: SqlitePool) -> IntermediateModelKnot:
    return IntermediateModelKnot(
        source_pool=pool,
        left_table=_LEFT_TABLE,
        right_table=_RIGHT_TABLE,
        join_type=_JOIN_TYPE,
        join_condition=_JOIN_CONDITION,
        select_expression=_SELECT_EXPRESSION,
        target_pool=pool,
        target_table=_TARGET_TABLE,
        _config=KnotConfig(id="int"),
    )


class TestIntermediateModelKnot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_inner_join_produces_correct_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT order_id, customer_id, name FROM int_orders ORDER BY order_id"
        )
        assert rows == [(1, 10, "Alice"), (2, 11, "Bob")]

    async def test_left_join_type_accepted(self) -> None:
        with Tapestry() as t:
            IntermediateModelKnot(
                source_pool=self.pool,
                left_table=_LEFT_TABLE,
                right_table=_RIGHT_TABLE,
                join_type="left",
                join_condition=_JOIN_CONDITION,
                select_expression=_SELECT_EXPRESSION,
                target_pool=self.pool,
                target_table=_TARGET_TABLE,
                _config=KnotConfig(id="int-left"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded

    async def test_returns_rows_written(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["rows_written"] == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_join_condition_from_upstream_knot(self) -> None:
        @knot
        async def emit_condition() -> str:
            return _JOIN_CONDITION

        with Tapestry() as t:
            cond_knot = emit_condition(_config=KnotConfig(id="cond"))
            IntermediateModelKnot(
                source_pool=self.pool,
                left_table=_LEFT_TABLE,
                right_table=_RIGHT_TABLE,
                join_type=_JOIN_TYPE,
                join_condition=cond_knot,
                select_expression=_SELECT_EXPRESSION,
                target_pool=self.pool,
                target_table=_TARGET_TABLE,
                _config=KnotConfig(id="int"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["int"]["rows_written"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> IntermediateModelKnot:
        defaults: dict[str, Any] = {
            "source_pool": self.pool,
            "left_table": _LEFT_TABLE,
            "right_table": _RIGHT_TABLE,
            "join_type": _JOIN_TYPE,
            "join_condition": _JOIN_CONDITION,
            "select_expression": _SELECT_EXPRESSION,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return IntermediateModelKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: IntermediateModelKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.pool,
            "left_table": _LEFT_TABLE,
            "right_table": _RIGHT_TABLE,
            "join_type": _JOIN_TYPE,
            "join_condition": _JOIN_CONDITION,
            "select_expression": _SELECT_EXPRESSION,
            "target_pool": self.pool,
            "target_table": _TARGET_TABLE,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_invalid_join_type(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "join_type"):
            await self._call(k, join_type="CROSS")

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, left_table="stg orders")
