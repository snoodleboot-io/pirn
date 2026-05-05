"""Tests for :class:`NullRateMonitor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.null_rate_monitor import NullRateMonitor
from pirn.tapestry import Tapestry

_TABLE = "users"
_THRESHOLDS = {"email": 0.5, "phone": 0.5}


async def _make_pool() -> SqlitePool:
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
    return p


def _make_knot(pool: SqlitePool, thresholds: dict[str, float] | None = None) -> NullRateMonitor:
    return NullRateMonitor(
        pool=pool,
        monitored_table=_TABLE,
        column_thresholds=thresholds if thresholds is not None else _THRESHOLDS,
        _config=KnotConfig(id="nrm"),
    )


class TestNullRateMonitor(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_computes_correct_null_rate(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, {"email": 1.0, "phone": 1.0})
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert abs(out["null_rates"]["email"] - 0.5) < 0.01
        assert abs(out["null_rates"]["phone"] - 0.5) < 0.01

    async def test_reports_violation_when_null_rate_exceeds_threshold(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, {"email": 0.1})
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert len(out["violations"]) == 1
        assert out["violations"][0]["column"] == "email"

    async def test_no_violations_within_threshold(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, {"email": 0.9})
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["violations"] == []

    async def test_result_contains_monitored_table(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["monitored_table"] == _TABLE


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_column_thresholds_from_upstream_knot(self) -> None:
        @knot
        async def emit_thresholds() -> dict[str, float]:
            return {"email": 1.0}

        with Tapestry() as t:
            thresh_knot = emit_thresholds(_config=KnotConfig(id="th"))
            NullRateMonitor(
                pool=self.pool,
                monitored_table=_TABLE,
                column_thresholds=thresh_knot,
                _config=KnotConfig(id="nrm"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["nrm"]["violations"] == []


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> NullRateMonitor:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "column_thresholds": _THRESHOLDS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return NullRateMonitor(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: NullRateMonitor, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "column_thresholds": _THRESHOLDS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_thresholds(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_thresholds"):
            await self._call(k, column_thresholds={})

    async def test_rejects_empty_monitored_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "monitored_table"):
            await self._call(k, monitored_table="")
