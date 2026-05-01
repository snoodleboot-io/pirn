"""ATDD acceptance test: bronze → silver → gold medallion architecture."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.medallion.bronze_raw_ingest import (
    BronzeRawIngest,
)
from pirn.domains.data.specializations.medallion.gold_aggregation import (
    GoldAggregation,
)
from pirn.domains.data.specializations.medallion.silver_clean_transform import (
    SilverCleanTransform,
)
from pirn.domains.data.transforms.aggregate_spec import AggregateSpec
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE source_orders ("
        "  id INTEGER PRIMARY KEY,"
        "  region TEXT,"
        "  amount REAL"
        ")"
    )
    await p.execute_many(
        "INSERT INTO source_orders (id, region, amount) VALUES (?, ?, ?)",
        [
            (1, "EU", 10.0),
            (2, "EU", 25.0),
            (2, "EU", 25.0),     # duplicate; silver dedup kicks in
            (3, "US", 100.0),
            (4, "US", -1.0),     # silver filter drops negative amounts
        ],
    )
    await p.execute(
        "CREATE TABLE bronze_orders ("
        "  id INTEGER, region TEXT, amount REAL, "
        "  _ingested_at TEXT NOT NULL, _source_uri TEXT NOT NULL)"
    )
    await p.execute(
        "CREATE TABLE silver_orders ("
        "  id INTEGER PRIMARY KEY, region TEXT NOT NULL, amount REAL NOT NULL)"
    )
    await p.execute(
        "CREATE TABLE gold_region_totals ("
        "  region TEXT PRIMARY KEY, total_amount REAL NOT NULL)"
    )
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_bronze_silver_gold_pipeline(pool: SqlitePool) -> None:
    with Tapestry() as t1:
        BronzeRawIngest(
            source_pool=pool,
            source_query="SELECT id, region, amount FROM source_orders",
            target_pool=pool,
            target_table="bronze_orders",
            source_columns=("id", "region", "amount"),
            source_uri="memory://source_orders",
            _config=KnotConfig(id="bronze"),
        )
    r1 = await t1.run(RunRequest())
    assert r1.succeeded, [(rec.knot_id, rec.outcome) for rec in r1.lineage]
    bronze_rows = await pool.fetch_all("SELECT id FROM bronze_orders")
    assert len(bronze_rows) == 5

    with Tapestry() as t2:
        SilverCleanTransform(
            source_pool=pool,
            source_query="SELECT id, region, amount FROM bronze_orders",
            target_pool=pool,
            target_table="silver_orders",
            column_names=("id", "region", "amount"),
            casts={"id": int, "amount": float},
            filter_predicate=lambda row: row["amount"] > 0,
            primary_keys=("id",),
            _config=KnotConfig(id="silver"),
        )
    r2 = await t2.run(RunRequest())
    assert r2.succeeded
    silver_rows = await pool.fetch_all(
        "SELECT id, region, amount FROM silver_orders ORDER BY id"
    )
    assert silver_rows == [(1, "EU", 10.0), (2, "EU", 25.0), (3, "US", 100.0)]

    with Tapestry() as t3:
        GoldAggregation(
            source_pool=pool,
            source_query="SELECT id, region, amount FROM silver_orders",
            source_columns=("id", "region", "amount"),
            target_pool=pool,
            target_table="gold_region_totals",
            by=("region",),
            aggs={"total_amount": AggregateSpec(source="amount", function="sum")},
            _config=KnotConfig(id="gold"),
        )
    r3 = await t3.run(RunRequest())
    assert r3.succeeded
    gold_rows = await pool.fetch_all(
        "SELECT region, total_amount FROM gold_region_totals ORDER BY region"
    )
    assert gold_rows == [("EU", 35.0), ("US", 100.0)]
