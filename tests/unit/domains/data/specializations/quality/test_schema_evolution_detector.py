"""Tests for :class:`SchemaEvolutionDetector`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.schema_evolution_detector import (
    SchemaEvolutionDetector,
)
from pirn.tapestry import Tapestry

_TABLE = "orders"
_SCHEMA_QUERY = "SELECT name, type FROM pragma_table_info('orders') ORDER BY name"
_EXPECTED = {"id": "INTEGER", "amount": "REAL"}


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL NOT NULL)"
    )
    return p


def _make_knot(
    pool: SqlitePool,
    expected: dict[str, str] | None = None,
) -> SchemaEvolutionDetector:
    return SchemaEvolutionDetector(
        pool=pool,
        monitored_table=_TABLE,
        expected_schema=expected if expected is not None else _EXPECTED,
        schema_query=_SCHEMA_QUERY,
        _config=KnotConfig(id="sed"),
    )


class TestSchemaEvolutionDetector(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_no_change_when_schemas_match(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["schema_changed"] is False
        assert out["added_columns"] == []
        assert out["dropped_columns"] == []
        assert out["type_changes"] == []

    async def test_detects_added_column(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, {"id": "INTEGER"})
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["schema_changed"] is True
        assert "amount" in out["added_columns"]

    async def test_detects_dropped_column(self) -> None:
        with Tapestry() as t:
            k = _make_knot(
                self.pool,
                {"id": "INTEGER", "amount": "REAL", "customer_id": "INTEGER"},
            )
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["schema_changed"] is True
        assert "customer_id" in out["dropped_columns"]

    async def test_result_contains_monitored_table(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["monitored_table"] == _TABLE


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_schema_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SCHEMA_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            SchemaEvolutionDetector(
                pool=self.pool,
                monitored_table=_TABLE,
                expected_schema=_EXPECTED,
                schema_query=q_knot,
                _config=KnotConfig(id="sed"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sed"]["schema_changed"] is False


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> SchemaEvolutionDetector:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "expected_schema": _EXPECTED,
            "schema_query": _SCHEMA_QUERY,
        }
        defaults.update(kwargs)
        with Tapestry():
            return SchemaEvolutionDetector(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: SchemaEvolutionDetector, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "expected_schema": _EXPECTED,
            "schema_query": _SCHEMA_QUERY,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_expected_schema(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "expected_schema"):
            await self._call(k, expected_schema={})

    async def test_rejects_empty_schema_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "schema_query"):
            await self._call(k, schema_query="")
