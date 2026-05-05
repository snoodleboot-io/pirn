"""Tests for :class:`NullRateMonitor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.null_rate_monitor import (
    NullRateMonitor,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, phone TEXT)"
        )
        await p.execute_many(
            "INSERT INTO users (id, email, phone) VALUES (?, ?, ?)",
            [
                (1, "a@b.com", "123"),
                (2, None, "456"),
                (3, None, None),
                (4, "c@d.com", None),
            ],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            NullRateMonitor(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="users",
                column_thresholds={"email": 0.5},
                _config=KnotConfig(id="nrm"),
            )

    def test_rejects_empty_thresholds(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "column_thresholds"):
            NullRateMonitor(
                pool=pool,
                monitored_table="users",
                column_thresholds={},
                _config=KnotConfig(id="nrm"),
            )


class TestNullRateMonitorBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, phone TEXT)"
        )
        await p.execute_many(
            "INSERT INTO users (id, email, phone) VALUES (?, ?, ?)",
            [
                (1, "a@b.com", "123"),
                (2, None, "456"),
                (3, None, None),
                (4, "c@d.com", None),
            ],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_computes_correct_null_rate(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            knot = NullRateMonitor(
                pool=pool,
                monitored_table="users",
                column_thresholds={"email": 1.0, "phone": 1.0},
                _config=KnotConfig(id="nrm"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert abs(out["null_rates"]["email"] - 0.5) < 0.01
        assert abs(out["null_rates"]["phone"] - 0.5) < 0.01

    async def test_reports_violation_when_null_rate_exceeds_threshold(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            knot = NullRateMonitor(
                pool=pool,
                monitored_table="users",
                column_thresholds={"email": 0.1},
                _config=KnotConfig(id="nrm"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert len(out["violations"]) == 1
        assert out["violations"][0]["column"] == "email"

    async def test_no_violations_within_threshold(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            knot = NullRateMonitor(
                pool=pool,
                monitored_table="users",
                column_thresholds={"email": 0.9},
                _config=KnotConfig(id="nrm"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["violations"] == []
