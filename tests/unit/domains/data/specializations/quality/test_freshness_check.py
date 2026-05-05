"""Tests for :class:`FreshnessCheck`."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.freshness_check import (
    FreshnessCheck,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
        )
        now = datetime.now(timezone.utc).isoformat()
        await p.execute(
            "INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, now)
        )
        self.pool_fresh = p

    async def asyncTearDown(self) -> None:
        await self.pool_fresh.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            FreshnessCheck(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=3600,
                _config=KnotConfig(id="fresh"),
            )

    def test_rejects_invalid_max_age(self) -> None:
        pool_fresh = self.pool_fresh
        with self.assertRaisesRegex(ValueError, "max_age_seconds"):
            FreshnessCheck(
                pool=pool_fresh,
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=0,
                _config=KnotConfig(id="fresh"),
            )


class TestFreshnessCheckBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
        )
        self.pool_empty = p
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
        )
        now = datetime.now(timezone.utc).isoformat()
        await p.execute(
            "INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, now)
        )
        self.pool_fresh = p
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
        )
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        await p.execute(
            "INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, old)
        )
        self.pool_stale = p

    async def asyncTearDown(self) -> None:
        await self.pool_empty.close()
        
        
        await self.pool_fresh.close()
        
        
        await self.pool_stale.close()
        
        
    async def test_fresh_data_does_not_breach_sla(self) -> None:
        pool_fresh = self.pool_fresh
        with Tapestry() as t:
            knot = FreshnessCheck(
                pool=pool_fresh,
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=3600,
                _config=KnotConfig(id="fresh"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["sla_breached"] is False

    async def test_stale_data_breaches_sla(self) -> None:
        pool_stale = self.pool_stale
        with Tapestry() as t:
            knot = FreshnessCheck(
                pool=pool_stale,
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=3600,
                _config=KnotConfig(id="fresh"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["sla_breached"] is True

    async def test_fails_on_empty_table(self) -> None:
        pool_empty = self.pool_empty
        with Tapestry() as t:
            FreshnessCheck(
                pool=pool_empty,
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=3600,
                _config=KnotConfig(id="fresh"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
