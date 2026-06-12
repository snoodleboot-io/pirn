"""Tests for :class:`QueryNewRowsKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.query_new_rows_knot import (
    QueryNewRowsKnot,
)
from pirn.tapestry import Tapestry


async def _make_source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, updated_at TEXT)"
    )
    await pool.execute_many(
        "INSERT INTO orders (id, updated_at) VALUES (?, ?)",
        [(1, "2024-01-01"), (2, "2024-06-01")],
    )
    return pool


def _make_knot(pool: SqlitePool, hwm_knot: Any) -> QueryNewRowsKnot:
    return QueryNewRowsKnot(
        pool=pool,
        table="orders",
        columns=["id", "updated_at"],
        watermark_column="updated_at",
        high_water_mark=hwm_knot,
        _config=KnotConfig(id="qnr"),
    )


class TestQueryNewRowsKnot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_source_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_initial_load_returns_all_rows(self) -> None:
        @knot
        async def no_hwm() -> None:
            return None

        with Tapestry() as t:
            hwm = no_hwm(_config=KnotConfig(id="hwm"))
            _make_knot(self.pool, hwm)
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["qnr"] == [(1, "2024-01-01"), (2, "2024-06-01")]

    async def test_incremental_load_uses_where_clause(self) -> None:
        @knot
        async def hwm_value() -> str:
            return "2024-01-01"

        with Tapestry() as t:
            hwm = hwm_value(_config=KnotConfig(id="hwm"))
            _make_knot(self.pool, hwm)
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["qnr"] == [(2, "2024-06-01")]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_source_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_high_water_mark_from_upstream_knot(self) -> None:
        pool = self.pool

        @knot
        async def emit_pool() -> SqlitePool:
            return pool

        @knot
        async def emit_hwm() -> None:
            return None

        with Tapestry() as t:
            p_knot = emit_pool(_config=KnotConfig(id="pool"))
            hwm = emit_hwm(_config=KnotConfig(id="hwm"))
            QueryNewRowsKnot(
                pool=p_knot,
                table="orders",
                columns=["id", "updated_at"],
                watermark_column="updated_at",
                high_water_mark=hwm,
                _config=KnotConfig(id="qnr"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["qnr"]) == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_source_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> QueryNewRowsKnot:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "table": "orders",
            "columns": ["id", "updated_at"],
            "watermark_column": "updated_at",
            "high_water_mark": MagicMock(),
        }
        defaults.update(kwargs)
        with Tapestry():
            return QueryNewRowsKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: QueryNewRowsKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "table": "orders",
            "columns": ["id", "updated_at"],
            "watermark_column": "updated_at",
            "high_water_mark": None,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="not-a-pool")

    async def test_rejects_empty_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "table"):
            await self._call(k, table="")

    async def test_rejects_non_alphanumeric_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "alphanumeric"):
            await self._call(k, table="orders; DROP TABLE--")

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "columns"):
            await self._call(k, columns=[])

    async def test_rejects_empty_watermark_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "watermark_column"):
            await self._call(k, watermark_column="")
