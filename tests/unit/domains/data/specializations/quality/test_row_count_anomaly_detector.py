"""Tests for :class:`RowCountAnomalyDetector`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.row_count_anomaly_detector import (
    RowCountAnomalyDetector,
)
from pirn.tapestry import Tapestry

_TABLE = "events"
_AUDIT = "row_count_audit"


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE events (id INTEGER PRIMARY KEY)")
    await p.execute_many(
        "INSERT INTO events (id) VALUES (?)", [(i,) for i in range(10)]
    )
    await p.execute(
        "CREATE TABLE row_count_audit ("
        "  table_name TEXT NOT NULL,"
        "  row_count INTEGER NOT NULL,"
        "  recorded_at TEXT NOT NULL"
        ")"
    )
    return p


def _make_knot(pool: SqlitePool, threshold: float = 0.30) -> RowCountAnomalyDetector:
    return RowCountAnomalyDetector(
        pool=pool,
        monitored_table=_TABLE,
        audit_table=_AUDIT,
        threshold=threshold,
        _config=KnotConfig(id="rca"),
    )


class TestRowCountAnomalyDetector(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_first_run_returns_no_anomaly(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded

    async def test_detects_anomaly_when_count_drops_sharply(self) -> None:
        for _ in range(3):
            with Tapestry() as t:
                _make_knot(self.pool)
            await t.run(RunRequest())
        await self.pool.execute("DELETE FROM events WHERE id > 0")
        with Tapestry() as t2:
            k = _make_knot(self.pool)
        result = await t2.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["anomaly_detected"] is True

    async def test_no_anomaly_within_threshold(self) -> None:
        for _ in range(3):
            with Tapestry() as t:
                _make_knot(self.pool)
            await t.run(RunRequest())
        with Tapestry() as t2:
            k = _make_knot(self.pool)
        result = await t2.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["anomaly_detected"] is False

    async def test_result_contains_expected_keys(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert "current_count" in out
        assert "rolling_avg" in out
        assert out["monitored_table"] == _TABLE


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_threshold_from_upstream_knot(self) -> None:
        @knot
        async def emit_threshold() -> float:
            return 0.30

        with Tapestry() as t:
            th_knot = emit_threshold(_config=KnotConfig(id="th"))
            RowCountAnomalyDetector(
                pool=self.pool,
                monitored_table=_TABLE,
                audit_table=_AUDIT,
                threshold=th_knot,
                _config=KnotConfig(id="rca"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rca"]["anomaly_detected"] is False


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> RowCountAnomalyDetector:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "audit_table": _AUDIT,
            "window": 7,
            "threshold": 0.30,
        }
        defaults.update(kwargs)
        with Tapestry():
            return RowCountAnomalyDetector(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: RowCountAnomalyDetector, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "audit_table": _AUDIT,
            "window": 7,
            "threshold": 0.30,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_invalid_window(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window"):
            await self._call(k, window=0)

    async def test_rejects_invalid_threshold(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "threshold"):
            await self._call(k, threshold=-0.1)
