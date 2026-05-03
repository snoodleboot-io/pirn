"""Tests for :class:`SchemaEvolutionDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.schema_evolution_detector import (
    SchemaEvolutionDetector,
)
from pirn.tapestry import Tapestry

_SCHEMA_QUERY = (
    "SELECT name, type FROM pragma_table_info('orders') ORDER BY name"
)


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL NOT NULL)"
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            SchemaEvolutionDetector(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="orders",
                expected_schema={"id": "INTEGER"},
                schema_query=_SCHEMA_QUERY,
                _config=KnotConfig(id="sed"),
            )

    def test_rejects_empty_expected_schema(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="expected_schema"):
            SchemaEvolutionDetector(
                pool=pool,
                monitored_table="orders",
                expected_schema={},
                schema_query=_SCHEMA_QUERY,
                _config=KnotConfig(id="sed"),
            )


@pytest.mark.asyncio
class TestSchemaEvolutionDetectorBehaviour:
    async def test_no_change_when_schemas_match(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = SchemaEvolutionDetector(
                pool=pool,
                monitored_table="orders",
                expected_schema={"id": "INTEGER", "amount": "REAL"},
                schema_query=_SCHEMA_QUERY,
                _config=KnotConfig(id="sed"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["schema_changed"] is False
        assert out["added_columns"] == []
        assert out["dropped_columns"] == []
        assert out["type_changes"] == []

    async def test_detects_added_column(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = SchemaEvolutionDetector(
                pool=pool,
                monitored_table="orders",
                expected_schema={"id": "INTEGER"},
                schema_query=_SCHEMA_QUERY,
                _config=KnotConfig(id="sed"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["schema_changed"] is True
        assert "amount" in out["added_columns"]

    async def test_detects_dropped_column(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = SchemaEvolutionDetector(
                pool=pool,
                monitored_table="orders",
                expected_schema={
                    "id": "INTEGER",
                    "amount": "REAL",
                    "customer_id": "INTEGER",
                },
                schema_query=_SCHEMA_QUERY,
                _config=KnotConfig(id="sed"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["schema_changed"] is True
        assert "customer_id" in out["dropped_columns"]
