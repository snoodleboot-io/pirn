"""Tests for :class:`FreshnessCheck`."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.freshness_check import (
    FreshnessCheck,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool_fresh() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
    )
    now = datetime.now(timezone.utc).isoformat()
    await p.execute(
        "INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, now)
    )
    yield p
    await p.close()


@pytest.fixture
async def pool_stale() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
    )
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    await p.execute(
        "INSERT INTO events (id, updated_at) VALUES (?, ?)", (1, old)
    )
    yield p
    await p.close()


@pytest.fixture
async def pool_empty() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)"
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            FreshnessCheck(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=3600,
                _config=KnotConfig(id="fresh"),
            )

    def test_rejects_invalid_max_age(self, pool_fresh: SqlitePool) -> None:
        with pytest.raises(ValueError, match="max_age_seconds"):
            FreshnessCheck(
                pool=pool_fresh,
                monitored_table="events",
                timestamp_column="updated_at",
                max_age_seconds=0,
                _config=KnotConfig(id="fresh"),
            )


@pytest.mark.asyncio
class TestFreshnessCheckBehaviour:
    async def test_fresh_data_does_not_breach_sla(
        self, pool_fresh: SqlitePool
    ) -> None:
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

    async def test_stale_data_breaches_sla(
        self, pool_stale: SqlitePool
    ) -> None:
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

    async def test_fails_on_empty_table(self, pool_empty: SqlitePool) -> None:
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
