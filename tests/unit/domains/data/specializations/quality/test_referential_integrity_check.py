"""Tests for :class:`ReferentialIntegrityCheck`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.referential_integrity_check import (
    ReferentialIntegrityCheck,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"
    )
    await p.execute_many(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    await p.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER)"
    )
    await p.execute_many(
        "INSERT INTO orders (id, customer_id) VALUES (?, ?)",
        [(1, 1), (2, 2), (3, 99)],
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ReferentialIntegrityCheck(
                pool="bad",  # type: ignore[arg-type]
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )

    def test_rejects_invalid_fact_table(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            ReferentialIntegrityCheck(
                pool=pool,
                fact_table="bad table",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )


@pytest.mark.asyncio
class TestReferentialIntegrityCheckBehaviour:
    async def test_detects_orphaned_rows(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = ReferentialIntegrityCheck(
                pool=pool,
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["orphaned_rows"] == 1
        assert out["has_orphans"] is True
        assert abs(out["orphaned_pct"] - 100 / 3) < 0.01

    async def test_clean_table_has_no_orphans(self, pool: SqlitePool) -> None:
        await pool.execute("DELETE FROM orders WHERE id = 3")
        with Tapestry() as t:
            knot = ReferentialIntegrityCheck(
                pool=pool,
                fact_table="orders",
                fact_column="customer_id",
                dimension_table="customers",
                dimension_column="id",
                _config=KnotConfig(id="ri"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["orphaned_rows"] == 0
        assert out["has_orphans"] is False
