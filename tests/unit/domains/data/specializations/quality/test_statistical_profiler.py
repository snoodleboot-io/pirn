"""Tests for :class:`StatisticalProfiler`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.statistical_profiler import (
    StatisticalProfiler,
)
from pirn.tapestry import Tapestry

_TABLE = "metrics"
_COLUMNS = ("score",)


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE metrics ("
        "  id INTEGER PRIMARY KEY,"
        "  score REAL,"
        "  category TEXT"
        ")"
    )
    await p.execute_many(
        "INSERT INTO metrics (id, score, category) VALUES (?, ?, ?)",
        [
            (1, 10.0, "A"),
            (2, 20.0, "B"),
            (3, 30.0, "A"),
            (4, None, "C"),
            (5, 50.0, "B"),
        ],
    )
    return p


def _make_knot(
    pool: SqlitePool,
    columns: tuple[str, ...] | None = None,
    top_n: int = 5,
) -> StatisticalProfiler:
    return StatisticalProfiler(
        pool=pool,
        monitored_table=_TABLE,
        columns=columns if columns is not None else _COLUMNS,
        top_n=top_n,
        _config=KnotConfig(id="prof"),
    )


class TestStatisticalProfiler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_computes_numeric_stats(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["total_rows"] == 5
        profile = out["profiles"][0]
        assert profile["column"] == "score"
        assert abs(profile["min"] - 10.0) < 0.01
        assert abs(profile["max"] - 50.0) < 0.01
        assert abs(profile["null_rate"] - 0.2) < 0.01
        assert profile["cardinality"] == 4

    async def test_computes_top_values(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, ("category",), top_n=3)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        profile = out["profiles"][0]
        assert len(profile["top_values"]) <= 3
        top_vals = [tv["value"] for tv in profile["top_values"]]
        assert "A" in top_vals
        assert "B" in top_vals

    async def test_profiles_multiple_columns(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool, ("score", "category"))
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert len(out["profiles"]) == 2
        cols = [p["column"] for p in out["profiles"]]
        assert "score" in cols
        assert "category" in cols

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

    async def test_top_n_from_upstream_knot(self) -> None:
        @knot
        async def emit_top_n() -> int:
            return 3

        with Tapestry() as t:
            n_knot = emit_top_n(_config=KnotConfig(id="n"))
            StatisticalProfiler(
                pool=self.pool,
                monitored_table=_TABLE,
                columns=("category",),
                top_n=n_knot,
                _config=KnotConfig(id="prof"),
            )
        result = await t.run(RunRequest())
        profile = result.outputs["prof"]["profiles"][0]
        assert len(profile["top_values"]) <= 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> StatisticalProfiler:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "columns": _COLUMNS,
            "top_n": 5,
        }
        defaults.update(kwargs)
        with Tapestry():
            return StatisticalProfiler(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: StatisticalProfiler, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "monitored_table": _TABLE,
            "columns": _COLUMNS,
            "top_n": 5,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await self._call(k, columns=())

    async def test_rejects_invalid_top_n(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "top_n"):
            await self._call(k, top_n=0)
