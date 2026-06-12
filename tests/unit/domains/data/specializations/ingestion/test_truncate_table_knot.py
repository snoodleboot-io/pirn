"""Tests for :class:`TruncateTableKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.truncate_table_knot import (
    TruncateTableKnot,
)
from pirn.tapestry import Tapestry


async def _make_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, name TEXT)")
    await pool.execute_many(
        "INSERT INTO orders (id, name) VALUES (?, ?)",
        [(1, "a"), (2, "b")],
    )
    return pool


def _make_knot(pool: SqlitePool) -> TruncateTableKnot:
    return TruncateTableKnot(
        pool=pool,
        table="orders",
        _config=KnotConfig(id="truncate"),
    )


class TestTruncateTableKnot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_deletes_all_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all("SELECT COUNT(*) FROM orders")
        assert rows[0][0] == 0

    async def test_returns_table_name(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id] == "orders"

    async def test_underscore_table_name_accepted(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE raw_events (id INTEGER PRIMARY KEY)")
        with Tapestry() as t:
            TruncateTableKnot(
                pool=pool, table="raw_events", _config=KnotConfig(id="trunc")
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        await pool.close()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_pool_from_upstream_knot(self) -> None:
        pool = self.pool

        @knot
        async def emit_pool() -> SqlitePool:
            return pool

        with Tapestry() as t:
            p_knot = emit_pool(_config=KnotConfig(id="pool"))
            TruncateTableKnot(
                pool=p_knot, table="orders", _config=KnotConfig(id="trunc")
            )
        result = await t.run(RunRequest())
        assert result.succeeded


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> TruncateTableKnot:
        defaults: dict[str, Any] = {"pool": self.pool, "table": "orders"}
        defaults.update(kwargs)
        with Tapestry():
            return TruncateTableKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: TruncateTableKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {"pool": self.pool, "table": "orders"}
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
