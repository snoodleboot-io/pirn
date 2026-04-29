"""Real-backend tests for the Postgres backend.

Gated by ``pytest.mark.needs_postgres``.  Set ``PIRN_TEST_POSTGRES_URL``
to run; tests skip silently when it is absent.

These mirror ``test_postgres_mock.py`` but run against a genuine
Postgres server, adding concurrency and persistence tests that mocks
cannot cover.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from pirn import KnotConfig, Parameter, RunRequest, Tapestry, knot

pytestmark = pytest.mark.needs_postgres


# ------------------------------------------------------------- fixture


@pytest.fixture
async def pg_pool():
    dsn = os.environ.get("PIRN_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PIRN_TEST_POSTGRES_URL not set")
    import asyncpg

    pool = await asyncpg.create_pool(dsn)
    async with pool.acquire() as conn:
        await conn.execute("""
            DROP TABLE IF EXISTS lineage_inputs CASCADE;
            DROP TABLE IF EXISTS lineage CASCADE;
            DROP TABLE IF EXISTS runs CASCADE;
            DROP TABLE IF EXISTS knots CASCADE;
        """)
    yield pool
    await pool.close()


# ------------------------------------------------------------- helpers


@knot
async def _double(x: int) -> int:
    return x * 2


@knot
async def _add(x: int, y: int) -> int:
    return x + y


async def _run_simple_pipeline(history, value: int = 5):
    with Tapestry(history=history) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    return await t.run(RunRequest(parameters={"x": value}))


# ------------------------------------------------------------- history tests


async def test_postgres_history_record_run_and_get_round_trips(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    result = await _run_simple_pipeline(history)

    fetched = await history.get_run(result.run_id)
    assert fetched is not None
    assert fetched.run_id == result.run_id
    assert fetched.outputs == result.outputs
    assert fetched.succeeded == result.succeeded


async def test_postgres_history_get_run_returns_none_for_missing(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    await history._ensure_init()
    assert await history.get_run("no-such-run") is None


async def test_postgres_history_query_by_output_hash_finds_run(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    result = await _run_simple_pipeline(history)

    # Find any knot that produced an output hash.
    output_hash = next(
        rec.output_hash for rec in result.lineage if rec.output_hash
    )
    rows = await history.query_lineage_by_output_hash(output_hash)
    assert len(rows) >= 1
    assert any(r.run_id == result.run_id for r in rows)


async def test_postgres_history_query_by_output_hash_finds_duplicates(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    # Two runs with the same input produce the same output hash.
    result1 = await _run_simple_pipeline(history, value=5)
    result2 = await _run_simple_pipeline(history, value=5)

    output_hash = next(
        rec.output_hash for rec in result1.lineage if rec.output_hash
    )
    rows = await history.query_lineage_by_output_hash(output_hash)
    run_ids = {r.run_id for r in rows}
    assert result1.run_id in run_ids
    assert result2.run_id in run_ids


async def test_postgres_history_query_by_input_hash_uses_join(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    result = await _run_simple_pipeline(history)

    # The 'd' knot has the parameter as an input.
    d_rec = next(r for r in result.lineage if r.knot_id == "d")
    input_hash = next(iter(d_rec.parent_input_hashes.values()))
    rows = await history.query_lineage_by_input_hash(input_hash)
    assert len(rows) >= 1
    assert any(r.knot_id == "d" and r.run_id == result.run_id for r in rows)


async def test_postgres_history_query_by_knot_id(pg_pool):
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    result = await _run_simple_pipeline(history)

    rows = await history.query_lineage_by_knot_id("d")
    assert len(rows) >= 1
    assert any(r.run_id == result.run_id for r in rows)


async def test_postgres_history_concurrent_writes(pg_pool):
    """100 parallel record_run calls must all succeed without contention."""
    from pirn.backends.postgres import PostgresHistory

    history = PostgresHistory(pool=pg_pool)
    await history._ensure_init()

    async def one_run(i: int):
        with Tapestry(history=history) as t:
            p = Parameter("x", int, _config=KnotConfig(id=f"x_{i}"))
            _double(x=p, _config=KnotConfig(id=f"d_{i}"))
        return await t.run(RunRequest(parameters={"x": i}))

    results = await asyncio.gather(*[one_run(i) for i in range(100)])
    assert len(results) == 100
    assert all(r.succeeded for r in results)

    # Verify row count via raw SQL.
    async with pg_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM runs")
    assert count == 100


async def test_postgres_history_persistence_across_connections(pg_pool):
    """Write with one pool, open a new pool, read data back.

    Catches missing commit calls — a mock can't verify this.
    """
    dsn = os.environ.get("PIRN_TEST_POSTGRES_URL")

    from pirn.backends.postgres import PostgresHistory

    history1 = PostgresHistory(pool=pg_pool)
    result = await _run_simple_pipeline(history1)

    # Open a second independent pool to the same DSN.
    import asyncpg

    pool2 = await asyncpg.create_pool(dsn)
    try:
        history2 = PostgresHistory(pool=pool2)
        fetched = await history2.get_run(result.run_id)
        assert fetched is not None
        assert fetched.run_id == result.run_id
    finally:
        await pool2.close()


# ------------------------------------------------------------- store tests


async def test_postgres_store_register_round_trips(pg_pool):
    from pirn.backends.postgres import PostgresStore

    store = PostgresStore(pool=pg_pool)
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    await store.aregister(p)

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT knot_id FROM knots WHERE knot_id = 'x'")
    assert row is not None


async def test_postgres_store_register_handles_id_conflict_idempotent(pg_pool):
    """Registering the same knot instance twice is idempotent."""
    from pirn.backends.postgres import PostgresStore

    store = PostgresStore(pool=pg_pool)
    with Tapestry(store=store) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
    # aregister same instance again — should not raise.
    await store.aregister(p)


async def test_postgres_store_register_raises_on_id_conflict_different_instance(
    pg_pool,
):
    """Registering a different knot with the same id must raise."""
    from pirn.backends.postgres import PostgresStore

    store = PostgresStore(pool=pg_pool)
    with Tapestry(store=store):
        p1 = Parameter("x", int, _config=KnotConfig(id="conflict"))

    store2 = PostgresStore(pool=pg_pool)
    with Tapestry(store=store2):
        p2 = Parameter("x", int, _config=KnotConfig(id="conflict"))

    # Register p1 into a fresh store that shares the pool.
    store3 = PostgresStore(pool=pg_pool)
    await store3.aregister(p1)

    # Registering p2 (different instance, same id) must raise.
    with pytest.raises(ValueError, match="conflict"):
        await store3.aregister(p2)
