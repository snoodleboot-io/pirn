"""ATDD acceptance test: ``ScdType2History`` end-to-end.

Three runs over a SQLite source/target pair:

1. **First run** — target empty. Every source row is inserted as the
   active version with ``is_current = 1`` and ``valid_to = NULL``.
2. **Second run** — source unchanged. No new rows; no rows closed out.
3. **Third run** — one source row's tracked column changes. The prior
   active row is closed out (``is_current = 0`` plus a ``valid_to``
   stamp) and a new active row is appended.

Asserts: history is preserved (we still see the earlier value with
``is_current=0``); only one row per key is current at any time.
"""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_2_history import (
    ScdType2History,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE source_customers ("
        "  customer_id INTEGER PRIMARY KEY,"
        "  region TEXT NOT NULL,"
        "  tier TEXT NOT NULL"
        ")"
    )
    await p.execute(
        "CREATE TABLE dim_customers_history ("
        "  customer_id INTEGER NOT NULL,"
        "  region TEXT NOT NULL,"
        "  tier TEXT NOT NULL,"
        "  valid_from TEXT NOT NULL,"
        "  valid_to TEXT,"
        "  is_current INTEGER NOT NULL"
        ")"
    )
    await p.execute_many(
        "INSERT INTO source_customers (customer_id, region, tier) "
        "VALUES (?, ?, ?)",
        [
            (1, "EU", "gold"),
            (2, "US", "silver"),
        ],
    )
    yield p
    await p.close()


def _build_pipeline(pool: SqlitePool) -> Tapestry:
    with Tapestry() as t:
        ScdType2History(
            source_pool=pool,
            source_query=(
                "SELECT customer_id, region, tier FROM source_customers"
            ),
            target_pool=pool,
            target_table="dim_customers_history",
            key_columns=("customer_id",),
            tracked_columns=("region", "tier"),
            _config=KnotConfig(id="scd2"),
        )
    return t


@pytest.mark.asyncio
async def test_scd_type_2_history_first_run_inserts_all(
    pool: SqlitePool,
) -> None:
    r1 = await _build_pipeline(pool).run(RunRequest())
    assert r1.succeeded, [(rec.knot_id, rec.outcome) for rec in r1.lineage]
    rows = await pool.fetch_all(
        "SELECT customer_id, region, tier, is_current "
        "FROM dim_customers_history ORDER BY customer_id"
    )
    assert rows == [
        (1, "EU", "gold", 1),
        (2, "US", "silver", 1),
    ]


@pytest.mark.asyncio
async def test_scd_type_2_history_idempotent_when_source_unchanged(
    pool: SqlitePool,
) -> None:
    await _build_pipeline(pool).run(RunRequest())
    await _build_pipeline(pool).run(RunRequest())
    rows = await pool.fetch_all(
        "SELECT customer_id FROM dim_customers_history ORDER BY customer_id"
    )
    assert rows == [(1,), (2,)]


@pytest.mark.asyncio
async def test_scd_type_2_history_closes_out_and_inserts_on_change(
    pool: SqlitePool,
) -> None:
    await _build_pipeline(pool).run(RunRequest())
    # Customer 1's tier changes; customer 2 untouched.
    await pool.execute(
        "UPDATE source_customers SET tier = ? WHERE customer_id = ?",
        ("platinum", 1),
    )
    await _build_pipeline(pool).run(RunRequest())
    rows = await pool.fetch_all(
        "SELECT customer_id, region, tier, is_current "
        "FROM dim_customers_history "
        "ORDER BY customer_id, valid_from"
    )
    # Customer 1 has two rows: closed-out (is_current=0) + new active.
    assert rows == [
        (1, "EU", "gold", 0),
        (1, "EU", "platinum", 1),
        (2, "US", "silver", 1),
    ]
    closed_outs = await pool.fetch_all(
        "SELECT customer_id FROM dim_customers_history "
        "WHERE is_current = 0"
    )
    assert closed_outs == [(1,)]
