"""Tests for :class:`DatabaseTableFreshnessCheck`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.database_table_freshness_check import DatabaseTableFreshnessCheck
from pirn.tapestry import Tapestry

_TABLE = "events"
_TS_COL = "updated_at"
_MAX_AGE = 3600


async def _make_pool(*, fresh: bool = True) -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
    )
    if fresh:
        ts = datetime.now(UTC).isoformat()
    else:
        ts = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    await p.execute("INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, ts))
    return p


async def _make_empty_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
    )
    return p


def _make_knot(pool: SqlitePool) -> DatabaseTableFreshnessCheck:
    return DatabaseTableFreshnessCheck(
        pool=pool,
        monitored_table=_TABLE,
        timestamp_column=_TS_COL,
        max_age_seconds=_MAX_AGE,
        _config=KnotConfig(id="fresh"),
    )


class TestFreshnessCheck(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool_fresh = await _make_pool(fresh=True)
        self.pool_stale = await _make_pool(fresh=False)
        self.pool_empty = await _make_empty_pool()

    async def asyncTearDown(self) -> None:
        await self.pool_fresh.close()
        await self.pool_stale.close()
        await self.pool_empty.close()

    async def test_fresh_data_does_not_breach_sla(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool_fresh)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["sla_breached"] is False

    async def test_stale_data_breaches_sla(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool_stale)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["sla_breached"] is True

    async def test_fails_on_empty_table(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool_empty)
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_result_contains_expected_keys(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool_fresh)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert "age_seconds" in out
        assert "max_age_seconds" in out
        assert out["monitored_table"] == _TABLE


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool(fresh=True)

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_max_age_from_upstream_knot(self) -> None:
        @knot
        async def emit_age() -> int:
            return _MAX_AGE

        with Tapestry() as t:
            age_knot = emit_age(_config=KnotConfig(id="age"))
            DatabaseTableFreshnessCheck(
                pool=self.pool,
                monitored_table=_TABLE,
                timestamp_column=_TS_COL,
                max_age_seconds=age_knot,
                _config=KnotConfig(id="fresh"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["fresh"]["sla_breached"] is False


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool(fresh=True)

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> DatabaseTableFreshnessCheck:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "timestamp_column": _TS_COL,
            "max_age_seconds": _MAX_AGE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DatabaseTableFreshnessCheck(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DatabaseTableFreshnessCheck, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "timestamp_column": _TS_COL,
            "max_age_seconds": _MAX_AGE,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_invalid_max_age(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_age_seconds"):
            await self._call(k, max_age_seconds=0)

    async def test_rejects_empty_monitored_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "monitored_table"):
            await self._call(k, monitored_table="")

    async def test_rejects_empty_timestamp_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "timestamp_column"):
            await self._call(k, timestamp_column="")
