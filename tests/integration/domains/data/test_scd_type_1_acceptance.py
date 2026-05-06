"""ATDD acceptance test: ``ScdType1Overwrite`` end-to-end.

Two runs over a SQLite source/target pair:

1. **First run** — target empty. Every source row is inserted.
2. **Second run** — source mutates one row in place. The matching target
   row is updated; no new history row is created.

Asserts the target ends up with one row per natural key and the latest
non-key values overwrite earlier ones.
"""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_1_overwrite import (
    ScdType1Overwrite,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE source_customers ("
        "  customer_id INTEGER PRIMARY KEY,"
        "  full_name TEXT NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    await p.execute(
        "CREATE TABLE dim_customers ("
        "  customer_id INTEGER PRIMARY KEY,"
        "  full_name TEXT NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    await p.execute_many(
        "INSERT INTO source_customers (customer_id, full_name, region) "
        "VALUES (?, ?, ?)",
        [
            (1, "Alice", "EU"),
            (2, "Bob", "US"),
            (3, "Carol", "AP"),
        ],
    )
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_scd_type_1_overwrite_first_then_update(pool: SqlitePool) -> None:
    with Tapestry() as t1:
        ScdType1Overwrite(
            source_pool=pool,
            source_query=(
                "SELECT customer_id, full_name, region FROM source_customers"
            ),
            target_pool=pool,
            target_table="dim_customers",
            key_columns=("customer_id",),
            non_key_columns=("full_name", "region"),
            _config=KnotConfig(id="scd1"),
        )
    r1 = await t1.run(RunRequest())
    assert r1.succeeded, [(rec.knot_id, rec.outcome) for rec in r1.lineage]
    after_first = await pool.fetch_all(
        "SELECT customer_id, full_name, region FROM dim_customers "
        "ORDER BY customer_id"
    )
    assert after_first == [
        (1, "Alice", "EU"),
        (2, "Bob", "US"),
        (3, "Carol", "AP"),
    ]

    # Mutate the source: Bob moves to EU, name typo fix on Carol.
    await pool.execute(
        "UPDATE source_customers SET region = ? WHERE customer_id = ?",
        ("EU", 2),
    )
    await pool.execute(
        "UPDATE source_customers SET full_name = ? WHERE customer_id = ?",
        ("Carolyn", 3),
    )

    with Tapestry() as t2:
        ScdType1Overwrite(
            source_pool=pool,
            source_query=(
                "SELECT customer_id, full_name, region FROM source_customers"
            ),
            target_pool=pool,
            target_table="dim_customers",
            key_columns=("customer_id",),
            non_key_columns=("full_name", "region"),
            _config=KnotConfig(id="scd1"),
        )
    r2 = await t2.run(RunRequest())
    assert r2.succeeded
    after_second = await pool.fetch_all(
        "SELECT customer_id, full_name, region FROM dim_customers "
        "ORDER BY customer_id"
    )
    # Only one row per natural key — Type 1 overwrites, never accumulates.
    assert after_second == [
        (1, "Alice", "EU"),
        (2, "Bob", "EU"),
        (3, "Carolyn", "AP"),
    ]
