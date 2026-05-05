"""Tests for :class:`TruncateTableKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.ingestion.truncate_table_knot import (
    TruncateTableKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.execute = AsyncMock(return_value=None)
    return pool


class TestTruncateTableKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        pool = _make_pool()
        knot = TruncateTableKnot(
            pool=pool,
            table="orders",
            _config=KnotConfig(id="truncate"),
        )
        self.assertIsInstance(knot, TruncateTableKnot)
        self.assertEqual(knot.table, "orders")

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            TruncateTableKnot(
                pool="not-a-pool",  # type: ignore[arg-type]
                table="orders",
                _config=KnotConfig(id="truncate"),
            )

    def test_rejects_empty_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            TruncateTableKnot(
                pool=pool,
                table="",
                _config=KnotConfig(id="truncate"),
            )

    def test_rejects_non_alphanumeric_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            TruncateTableKnot(
                pool=pool,
                table="orders; DROP TABLE--",
                _config=KnotConfig(id="truncate"),
            )


class TestTruncateTableKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_table_name(self) -> None:
        pool = _make_pool()
        knot = TruncateTableKnot(
            pool=pool,
            table="orders",
            _config=KnotConfig(id="truncate"),
        )
        result = await knot.process(**{})
        self.assertEqual(result, "orders")

    async def test_calls_execute_with_delete(self) -> None:
        pool = _make_pool()
        knot = TruncateTableKnot(
            pool=pool,
            table="orders",
            _config=KnotConfig(id="truncate"),
        )
        await knot.process(**{})
        pool.execute.assert_called_once()
        call_sql = pool.execute.call_args[0][0]
        self.assertIn("DELETE FROM", call_sql)
        self.assertIn("orders", call_sql)

    async def test_underscore_table_name_accepted(self) -> None:
        pool = _make_pool()
        knot = TruncateTableKnot(
            pool=pool,
            table="raw_events",
            _config=KnotConfig(id="truncate"),
        )
        result = await knot.process(**{})
        self.assertEqual(result, "raw_events")
