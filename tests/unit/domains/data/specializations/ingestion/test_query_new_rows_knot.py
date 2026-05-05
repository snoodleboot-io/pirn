"""Tests for :class:`QueryNewRowsKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.ingestion.query_new_rows_knot import (
    QueryNewRowsKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    return pool


class TestQueryNewRowsKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        pool = _make_pool()
        knot = QueryNewRowsKnot(
            pool=pool,
            table="orders",
            columns=["id", "updated_at"],
            watermark_column="updated_at",
            high_water_mark=MagicMock(),
            _config=KnotConfig(id="qnr"),
        )
        self.assertIsInstance(knot, QueryNewRowsKnot)

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            QueryNewRowsKnot(
                pool="not-a-pool",  # type: ignore[arg-type]
                table="orders",
                columns=["id"],
                watermark_column="updated_at",
                high_water_mark=MagicMock(),
                _config=KnotConfig(id="qnr"),
            )

    def test_rejects_empty_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            QueryNewRowsKnot(
                pool=pool,
                table="",
                columns=["id"],
                watermark_column="updated_at",
                high_water_mark=MagicMock(),
                _config=KnotConfig(id="qnr"),
            )

    def test_rejects_non_alphanumeric_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            QueryNewRowsKnot(
                pool=pool,
                table="orders; DROP TABLE--",
                columns=["id"],
                watermark_column="updated_at",
                high_water_mark=MagicMock(),
                _config=KnotConfig(id="qnr"),
            )

    def test_rejects_empty_columns(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            QueryNewRowsKnot(
                pool=pool,
                table="orders",
                columns=[],
                watermark_column="updated_at",
                high_water_mark=MagicMock(),
                _config=KnotConfig(id="qnr"),
            )

    def test_rejects_empty_watermark_column(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            QueryNewRowsKnot(
                pool=pool,
                table="orders",
                columns=["id"],
                watermark_column="",
                high_water_mark=MagicMock(),
                _config=KnotConfig(id="qnr"),
            )


class TestQueryNewRowsKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_initial_load_uses_full_select(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(1, "2024-01-01")])
        knot = QueryNewRowsKnot(
            pool=pool,
            table="orders",
            columns=["id", "updated_at"],
            watermark_column="updated_at",
            high_water_mark=MagicMock(),
            _config=KnotConfig(id="qnr"),
        )
        result = await knot.process(high_water_mark=None, **{})
        self.assertEqual(result, [(1, "2024-01-01")])
        call_args = pool.fetch_all.call_args
        query = call_args[0][0]
        self.assertIn("SELECT", query)
        self.assertNotIn("WHERE", query)

    async def test_incremental_load_uses_where_clause(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[(2, "2024-01-02")])
        knot = QueryNewRowsKnot(
            pool=pool,
            table="orders",
            columns=["id", "updated_at"],
            watermark_column="updated_at",
            high_water_mark=MagicMock(),
            _config=KnotConfig(id="qnr"),
        )
        result = await knot.process(high_water_mark="2024-01-01", **{})
        self.assertEqual(result, [(2, "2024-01-02")])
        call_args = pool.fetch_all.call_args
        query = call_args[0][0]
        self.assertIn("WHERE", query)

    async def test_raises_when_pool_has_no_fetch_all(self) -> None:
        pool = _make_pool()
        del pool.fetch_all
        knot = QueryNewRowsKnot(
            pool=pool,
            table="orders",
            columns=["id"],
            watermark_column="updated_at",
            high_water_mark=MagicMock(),
            _config=KnotConfig(id="qnr"),
        )
        with self.assertRaises(TypeError):
            await knot.process(high_water_mark=None, **{})
