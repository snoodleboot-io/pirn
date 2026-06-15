"""ATDD acceptance test: ``WatermarkIncrementalExtract`` end-to-end.

Two runs over a SQLite source/target pair:

1. **First run** — target empty. Extract reads everything from source,
   loads it into target.
2. **Second run** — source gains new rows. Extract reads only the rows
   newer than the target's high-water mark and appends them.

Asserts the second run did NOT re-load the old rows (no duplicates) and
DID load the new ones — the defining property of incremental extraction.
"""

from __future__ import annotations

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.ingestion.watermark_incremental_extract import (
    WatermarkIncrementalExtract,
)


@pytest.fixture
async def source_pool():
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE orders ("
        "  id INTEGER PRIMARY KEY,"
        "  amount REAL NOT NULL,"
        "  updated_at INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO orders (id, amount, updated_at) VALUES (?, ?, ?)",
        [(1, 10.0, 100), (2, 20.0, 110), (3, 30.0, 120)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool():
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE orders ("
        "  id INTEGER PRIMARY KEY,"
        "  amount REAL NOT NULL,"
        "  updated_at INTEGER NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


def _build_pipeline(*, source_pool, target_pool) -> Tapestry:
    with Tapestry() as t:
        WatermarkIncrementalExtract(
            source_pool=source_pool,
            source_table="orders",
            columns=("id", "amount", "updated_at"),
            target_pool=target_pool,
            target_table="orders",
            watermark_column="updated_at",
            _config=KnotConfig(id="incremental"),
        )
    return t


@pytest.mark.asyncio
async def test_first_run_loads_everything_then_second_run_only_new(
    source_pool, target_pool
) -> None:
    t1 = _build_pipeline(source_pool=source_pool, target_pool=target_pool)
    result1 = await t1.run(RunRequest())
    assert result1.succeeded, [(r.knot_id, r.outcome) for r in result1.lineage]

    after_first = await target_pool.fetch_all(
        "SELECT id, amount, updated_at FROM orders ORDER BY id"
    )
    assert after_first == [(1, 10.0, 100), (2, 20.0, 110), (3, 30.0, 120)]

    await source_pool.execute_many(
        "INSERT INTO orders (id, amount, updated_at) VALUES (?, ?, ?)",
        [(4, 40.0, 130), (5, 50.0, 140)],
    )

    t2 = _build_pipeline(source_pool=source_pool, target_pool=target_pool)
    result2 = await t2.run(RunRequest())
    assert result2.succeeded

    after_second = await target_pool.fetch_all(
        "SELECT id, amount, updated_at FROM orders ORDER BY id"
    )
    assert after_second == [
        (1, 10.0, 100),
        (2, 20.0, 110),
        (3, 30.0, 120),
        (4, 40.0, 130),
        (5, 50.0, 140),
    ]
