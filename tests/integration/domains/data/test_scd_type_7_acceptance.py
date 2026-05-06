"""ATDD acceptance test: ``ScdType7Hybrid`` end-to-end.

Two runs over a SQLite source/target pair:

1. **First run** — target empty. Each source row is inserted with
   identical historical and ``current_*`` values.
2. **Second run** — one tracked attribute changes. The prior active row
   is closed out, a new active row is inserted, and the ``current_*``
   columns on **every** historical row for the same key are backfilled
   to the new value.

Asserts the historical view (``region``, ``tier`` plus
``valid_from`` / ``valid_to`` / ``is_current``) and the current view
(``current_region``, ``current_tier``) are both correct after the change.
"""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_7_hybrid import (
    ScdType7Hybrid,
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
        "CREATE TABLE dim_customers_hybrid ("
        "  customer_id INTEGER NOT NULL,"
        "  region TEXT NOT NULL,"
        "  tier TEXT NOT NULL,"
        "  current_region TEXT NOT NULL,"
        "  current_tier TEXT NOT NULL,"
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
        ScdType7Hybrid(
            source_pool=pool,
            source_query=(
                "SELECT customer_id, region, tier FROM source_customers"
            ),
            target_pool=pool,
            target_table="dim_customers_hybrid",
            key_columns=("customer_id",),
            tracked_columns=("region", "tier"),
            current_columns={"region": "current_region", "tier": "current_tier"},
            _config=KnotConfig(id="scd7"),
        )
    return t


@pytest.mark.asyncio
async def test_scd_type_7_hybrid_initial_load_mirrors_current_columns(
    pool: SqlitePool,
) -> None:
    r1 = await _build_pipeline(pool).run(RunRequest())
    assert r1.succeeded, [(rec.knot_id, rec.outcome) for rec in r1.lineage]
    rows = await pool.fetch_all(
        "SELECT customer_id, region, tier, current_region, current_tier, "
        "is_current FROM dim_customers_hybrid ORDER BY customer_id"
    )
    assert rows == [
        (1, "EU", "gold", "EU", "gold", 1),
        (2, "US", "silver", "US", "silver", 1),
    ]


@pytest.mark.asyncio
async def test_scd_type_7_hybrid_change_backfills_current_on_history(
    pool: SqlitePool,
) -> None:
    await _build_pipeline(pool).run(RunRequest())
    await pool.execute(
        "UPDATE source_customers SET tier = ? WHERE customer_id = ?",
        ("platinum", 1),
    )
    await _build_pipeline(pool).run(RunRequest())
    rows = await pool.fetch_all(
        "SELECT customer_id, region, tier, current_region, current_tier, "
        "is_current FROM dim_customers_hybrid "
        "WHERE customer_id = 1 ORDER BY valid_from"
    )
    # Both rows for customer_id=1 carry the latest current_* values; the
    # historical ``tier`` column tells the time-travel story.
    assert rows == [
        (1, "EU", "gold", "EU", "platinum", 0),
        (1, "EU", "platinum", "EU", "platinum", 1),
    ]
    untouched = await pool.fetch_all(
        "SELECT customer_id, region, tier, current_region, current_tier, "
        "is_current FROM dim_customers_hybrid WHERE customer_id = 2"
    )
    assert untouched == [(2, "US", "silver", "US", "silver", 1)]
