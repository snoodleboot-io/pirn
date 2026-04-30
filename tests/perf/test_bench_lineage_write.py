"""Benchmark: lineage write throughput for SQLite and (optionally) Postgres.

SQLite runs in-process with no external dependencies. Postgres benchmarks
are gated by PIRN_TEST_POSTGRES_URL.

Run with:
    pytest tests/perf/bench_lineage_write.py --benchmark-only
    pytest tests/perf/bench_lineage_write.py --benchmark-only --real  # includes postgres
"""

from __future__ import annotations

import asyncio
import os

import pytest

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def _double(x: int) -> int:
    return x * 2


async def _run_n(history, n: int) -> None:
    with Tapestry(history=history) as t:
        p = Parameter("x", int, _config=KnotConfig(id="p"))
        _double(x=p, _config=KnotConfig(id="d"))
    for i in range(n):
        await t.run(RunRequest(parameters={"x": i}))


@pytest.mark.benchmark(group="lineage-sqlite")
def test_bench_sqlite_lineage_10(benchmark):
    history = SQLiteHistory(path=":memory:")
    benchmark(lambda: asyncio.run(_run_n(history, 10)))


@pytest.mark.benchmark(group="lineage-sqlite")
def test_bench_sqlite_lineage_100(benchmark):
    history = SQLiteHistory(path=":memory:")
    benchmark(lambda: asyncio.run(_run_n(history, 100)))


@pytest.mark.benchmark(group="lineage-sqlite")
def test_bench_sqlite_lineage_1000(benchmark):
    history = SQLiteHistory(path=":memory:")
    benchmark(lambda: asyncio.run(_run_n(history, 1000)))


@pytest.mark.needs_postgres
@pytest.mark.benchmark(group="lineage-postgres")
def test_bench_postgres_lineage_100(benchmark):
    dsn = os.environ.get("PIRN_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PIRN_TEST_POSTGRES_URL not set")

    import asyncpg

    from pirn.backends.postgres.postgres_history import PostgresHistory

    async def run():
        pool = await asyncpg.create_pool(dsn)
        history = PostgresHistory(pool=pool)
        await _run_n(history, 100)
        await pool.close()

    benchmark(lambda: asyncio.run(run()))


@pytest.mark.needs_postgres
@pytest.mark.benchmark(group="lineage-postgres")
def test_bench_postgres_lineage_1000(benchmark):
    dsn = os.environ.get("PIRN_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PIRN_TEST_POSTGRES_URL not set")

    import asyncpg

    from pirn.backends.postgres.postgres_history import PostgresHistory

    async def run():
        pool = await asyncpg.create_pool(dsn)
        history = PostgresHistory(pool=pool)
        await _run_n(history, 1000)
        await pool.close()

    benchmark(lambda: asyncio.run(run()))
