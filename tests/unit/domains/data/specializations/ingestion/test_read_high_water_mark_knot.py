"""Tests for :class:`ReadHighWaterMarkKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.ingestion.read_high_water_mark_knot import (
    ReadHighWaterMarkKnot,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    pool.fetch_all = AsyncMock(return_value=[])
    return pool


class TestReadHighWaterMarkKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        pool = _make_pool()
        knot = ReadHighWaterMarkKnot(
            pool=pool,
            table="events",
            watermark_column="loaded_at",
            _config=KnotConfig(id="hwm"),
        )
        self.assertIsInstance(knot, ReadHighWaterMarkKnot)

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            ReadHighWaterMarkKnot(
                pool="not-a-pool",  # type: ignore[arg-type]
                table="events",
                watermark_column="loaded_at",
                _config=KnotConfig(id="hwm"),
            )

    def test_rejects_empty_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            ReadHighWaterMarkKnot(
                pool=pool,
                table="",
                watermark_column="loaded_at",
                _config=KnotConfig(id="hwm"),
            )

    def test_rejects_non_alphanumeric_table(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            ReadHighWaterMarkKnot(
                pool=pool,
                table="events; DROP TABLE--",
                watermark_column="loaded_at",
                _config=KnotConfig(id="hwm"),
            )

    def test_rejects_empty_watermark_column(self) -> None:
        pool = _make_pool()
        with self.assertRaises(ValueError):
            ReadHighWaterMarkKnot(
                pool=pool,
                table="events",
                watermark_column="",
                _config=KnotConfig(id="hwm"),
            )


class TestReadHighWaterMarkKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_none_when_table_empty(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[])
        knot = ReadHighWaterMarkKnot(
            pool=pool,
            table="events",
            watermark_column="loaded_at",
            _config=KnotConfig(id="hwm"),
        )
        result = await knot.process(**{})
        self.assertIsNone(result)

    async def test_returns_max_value(self) -> None:
        pool = _make_pool()
        pool.fetch_all = AsyncMock(return_value=[("2024-06-01T00:00:00",)])
        knot = ReadHighWaterMarkKnot(
            pool=pool,
            table="events",
            watermark_column="loaded_at",
            _config=KnotConfig(id="hwm"),
        )
        result = await knot.process(**{})
        self.assertEqual(result, "2024-06-01T00:00:00")

    async def test_raises_when_pool_has_no_fetch_all(self) -> None:
        pool = _make_pool()
        del pool.fetch_all
        knot = ReadHighWaterMarkKnot(
            pool=pool,
            table="events",
            watermark_column="loaded_at",
            _config=KnotConfig(id="hwm"),
        )
        with self.assertRaises(TypeError):
            await knot.process(**{})
