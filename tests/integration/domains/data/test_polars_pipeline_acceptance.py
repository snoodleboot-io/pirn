"""ATDD acceptance test: extract → Tier-1→Tier-2 bridge → Polars filter +
aggregate → Tier-2→Tier-1 bridge → SQLite sink.

Demonstrates the canonical pirn pattern for mixing tiers:

1. A Tier-1 source emits a small :class:`DataBatch` of orders.
2. ``DataBatchToPolars`` upgrades to a :class:`PolarsDataBatch` so the
   transform chain runs in native Polars expressions (vectorised, no
   per-row Python iteration).
3. ``PolarsFilter`` and ``PolarsAggregate`` apply native Polars
   operations.
4. ``PolarsToDataBatch`` brings the result back to Tier 1 so the existing
   :class:`DatabaseExecuteSink` can write it.
5. SQLite ends up with the per-region totals.

If any step regresses (PolarsDataBatch contract, bridge round-trip,
Polars expression dispatch, or sink composition), this test catches it.
"""

from __future__ import annotations

import polars as pl
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.bridges.data_batch_to_polars import (
    DataBatchToPolars,
)
from pirn.domains.data.frames.polars.bridges.polars_to_data_batch import (
    PolarsToDataBatch,
)
from pirn.domains.data.frames.polars.polars_aggregate import PolarsAggregate
from pirn.domains.data.frames.polars.polars_filter import PolarsFilter
from pirn.tapestry import Tapestry


@knot
async def emit_orders() -> DataBatch:
    rows = (
        {"region": "EU", "amount": 10.0, "active": True},
        {"region": "EU", "amount": 25.0, "active": True},
        {"region": "EU", "amount": 5.0,  "active": False},   # excluded
        {"region": "US", "amount": 100.0, "active": True},
        {"region": "US", "amount": 50.0,  "active": True},
        {"region": "US", "amount": 1.0,   "active": False},  # excluded
    )
    return DataBatch(rows=rows, source_uri="memory://orders")


@knot
async def project_for_load(batch: DataBatch) -> list[tuple[str, float]]:
    return [(str(r["region"]), float(r["total"])) for r in batch.rows]


@pytest.mark.asyncio
async def test_tier1_to_polars_to_tier1_to_sqlite() -> None:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE region_totals ("
            "  region TEXT PRIMARY KEY, "
            "  total  REAL NOT NULL"
            ")"
        )

        with Tapestry() as t:
            extracted = emit_orders(_config=KnotConfig(id="extract"))
            polars_batch = DataBatchToPolars(
                batch=extracted, _config=KnotConfig(id="to_polars"),
            )
            active_only = PolarsFilter(
                batch=polars_batch,
                expression=pl.col("active"),
                _config=KnotConfig(id="active"),
            )
            totals = PolarsAggregate(
                batch=active_only,
                by=("region",),
                aggs=(pl.col("amount").sum().alias("total"),),
                _config=KnotConfig(id="totals"),
            )
            tier1_again = PolarsToDataBatch(
                batch=totals, _config=KnotConfig(id="to_tier1"),
            )
            rows = project_for_load(
                batch=tier1_again, _config=KnotConfig(id="project"),
            )
            DatabaseExecuteSink(
                pool=pool,
                query="INSERT INTO region_totals (region, total) VALUES (?, ?)",
                rows=rows,
                _config=KnotConfig(id="load"),
            )

        result = await t.run(RunRequest())
        assert result.succeeded, [
            (rec.knot_id, rec.outcome) for rec in result.lineage
        ]

        loaded = await pool.fetch_all(
            "SELECT region, total FROM region_totals ORDER BY region"
        )
        # EU active sum: 10 + 25 = 35
        # US active sum: 100 + 50 = 150
        assert loaded == [("EU", 35.0), ("US", 150.0)]

        # Confirm every knot in the pipeline ran.
        outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}
        for knot_id in (
            "extract", "to_polars", "active", "totals",
            "to_tier1", "project", "load",
        ):
            assert outcomes[knot_id] == "ok", outcomes
    finally:
        await pool.close()
