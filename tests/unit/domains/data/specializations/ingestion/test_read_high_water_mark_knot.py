"""Tests for :class:`ReadHighWaterMarkKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.read_high_water_mark_knot import (
    ReadHighWaterMarkKnot,
)
from pirn.tapestry import Tapestry


async def _make_pool(with_rows: bool = False) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, loaded_at TEXT)"
    )
    if with_rows:
        await pool.execute_many(
            "INSERT INTO events (id, loaded_at) VALUES (?, ?)",
            [(1, "2024-01-01"), (2, "2024-06-01")],
        )
    return pool


def _make_knot(pool: SqlitePool) -> ReadHighWaterMarkKnot:
    return ReadHighWaterMarkKnot(
        pool=pool,
        table="events",
        watermark_column="loaded_at",
        _config=KnotConfig(id="hwm"),
    )


class TestReadHighWaterMarkKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_none_when_empty(self) -> None:
        pool = await _make_pool(with_rows=False)
        with Tapestry() as t:
            _make_knot(pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["hwm"] is None
        await pool.close()

    async def test_returns_max_value(self) -> None:
        pool = await _make_pool(with_rows=True)
        with Tapestry() as t:
            _make_knot(pool)
        result = await t.run(RunRequest())
        assert result.outputs["hwm"] == "2024-06-01"
        await pool.close()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_pool_from_upstream_knot(self) -> None:
        pool = await _make_pool(with_rows=True)

        @knot
        async def emit_pool() -> SqlitePool:
            return pool

        with Tapestry() as t:
            p_knot = emit_pool(_config=KnotConfig(id="pool"))
            ReadHighWaterMarkKnot(
                pool=p_knot,
                table="events",
                watermark_column="loaded_at",
                _config=KnotConfig(id="hwm"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["hwm"] == "2024-06-01"
        await pool.close()


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> ReadHighWaterMarkKnot:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "table": "events",
            "watermark_column": "loaded_at",
        }
        defaults.update(kwargs)
        with Tapestry():
            return ReadHighWaterMarkKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ReadHighWaterMarkKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "table": "events",
            "watermark_column": "loaded_at",
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
            await self._call(k, table="events; DROP TABLE--")

    async def test_rejects_empty_watermark_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "watermark_column"):
            await self._call(k, watermark_column="")
