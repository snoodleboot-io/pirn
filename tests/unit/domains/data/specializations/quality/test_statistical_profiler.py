"""Tests for :class:`StatisticalProfiler`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.statistical_profiler import (
    StatisticalProfiler,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
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
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            StatisticalProfiler(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="metrics",
                columns=("score",),
                _config=KnotConfig(id="prof"),
            )

    def test_rejects_empty_columns(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            StatisticalProfiler(
                pool=pool,
                monitored_table="metrics",
                columns=(),
                _config=KnotConfig(id="prof"),
            )

    def test_rejects_invalid_top_n(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="top_n"):
            StatisticalProfiler(
                pool=pool,
                monitored_table="metrics",
                columns=("score",),
                top_n=0,
                _config=KnotConfig(id="prof"),
            )


@pytest.mark.asyncio
class TestStatisticalProfilerBehaviour:
    async def test_computes_numeric_stats(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = StatisticalProfiler(
                pool=pool,
                monitored_table="metrics",
                columns=("score",),
                _config=KnotConfig(id="prof"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["total_rows"] == 5
        profile = out["profiles"][0]
        assert profile["column"] == "score"
        assert abs(profile["min"] - 10.0) < 0.01
        assert abs(profile["max"] - 50.0) < 0.01
        assert abs(profile["null_rate"] - 0.2) < 0.01
        assert profile["cardinality"] == 4

    async def test_computes_top_values(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = StatisticalProfiler(
                pool=pool,
                monitored_table="metrics",
                columns=("category",),
                top_n=3,
                _config=KnotConfig(id="prof"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        profile = out["profiles"][0]
        assert len(profile["top_values"]) <= 3
        top_vals = [tv["value"] for tv in profile["top_values"]]
        assert "A" in top_vals
        assert "B" in top_vals

    async def test_profiles_multiple_columns(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            knot = StatisticalProfiler(
                pool=pool,
                monitored_table="metrics",
                columns=("score", "category"),
                _config=KnotConfig(id="prof"),
            )
        run_result = await t.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert len(out["profiles"]) == 2
        cols = [p["column"] for p in out["profiles"]]
        assert "score" in cols
        assert "category" in cols
