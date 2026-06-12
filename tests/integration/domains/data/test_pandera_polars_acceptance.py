"""ATDD acceptance test: Pandera validation embedded in a Tier-2 Polars
pipeline.

Demonstrates the canonical pattern for industrial-grade validation:

1. Source emits a Tier-1 :class:`DataBatch`.
2. Bridge to Tier-2 :class:`PolarsDataBatch`.
3. ``PanderaPolarsValidator`` validates against a rich Pandera schema
   (numeric ranges, string-length, allowed values) and emits a
   :class:`QualityReport`.
4. ``Gate(input=report, predicate=lambda r: r.passed)`` halts the
   pipeline when validation fails.
5. Downstream Polars transforms (``PolarsFilter``, ``PolarsAggregate``)
   only run on validated data.
6. ``PolarsToDataBatch`` brings the result back to Tier 1 and a
   ``DatabaseExecuteSink`` writes it to SQLite.

Two scenarios:
- Valid input → load runs, SQLite has the per-region totals.
- Invalid input → Gate closes, downstream knots show ``skipped`` in
  lineage, SQLite stays empty.
"""

from __future__ import annotations

import polars as pl
import pytest

pa = pytest.importorskip("pandera.polars")

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.bridges.data_batch_to_polars import (
    DataBatchToPolars,
)
from pirn.domains.data.frames.polars.bridges.polars_to_data_batch import (
    PolarsToDataBatch,
)
from pirn.domains.data.frames.polars.polars_aggregate import PolarsAggregate
from pirn.domains.data.frames.polars.polars_filter import PolarsFilter
from pirn.domains.data.quality_report import QualityReport
from pirn.domains.data.validation.pandera.pandera_polars_validator import (
    PanderaPolarsValidator,
)
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry


class _OrdersSchema(pa.DataFrameModel):
    region: str = pa.Field(isin=["EU", "US", "IN"])
    amount: float = pa.Field(ge=0.0)
    active: bool


@knot
async def emit_valid_orders() -> DataBatch:
    rows = (
        {"region": "EU", "amount": 10.0, "active": True},
        {"region": "EU", "amount": 25.0, "active": True},
        {"region": "EU", "amount": 5.0,  "active": False},   # filtered out
        {"region": "US", "amount": 100.0, "active": True},
        {"region": "US", "amount": 50.0,  "active": True},
    )
    return DataBatch(rows=rows, source_uri="memory://orders")


@knot
async def emit_invalid_orders() -> DataBatch:
    rows = (
        {"region": "EU",  "amount": 10.0, "active": True},
        {"region": "ZZ",  "amount": 25.0, "active": True},   # bad region
        {"region": "US",  "amount": -1.0, "active": True},   # bad amount
    )
    return DataBatch(rows=rows, source_uri="memory://orders")


@knot
async def project_for_load(batch: DataBatch) -> list[tuple[str, float]]:
    return [(str(r["region"]), float(r["total"])) for r in batch.rows]


def _build_pipeline(*, pool: SqlitePool, invalid: bool) -> Tapestry:
    extract = emit_invalid_orders if invalid else emit_valid_orders

    with Tapestry() as t:
        extracted = extract(_config=KnotConfig(id="extract"))
        polars_batch = DataBatchToPolars(
            batch=extracted, _config=KnotConfig(id="to_polars"),
        )
        report = PanderaPolarsValidator(
            batch=polars_batch,
            schema=_OrdersSchema,
            _config=KnotConfig(id="validate"),
        )
        ok_gate = Gate(
            input=report,
            predicate=lambda r: r.passed,
            _config=KnotConfig(id="validate_ok"),
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
            validate_ok=ok_gate,           # implicit dep
            _config=KnotConfig(id="load"),
        )
    return t


@pytest.mark.asyncio
async def test_valid_input_passes_pandera_and_loads_totals() -> None:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE region_totals ("
            "  region TEXT PRIMARY KEY, "
            "  total  REAL NOT NULL"
            ")"
        )
        t = _build_pipeline(pool=pool, invalid=False)
        result = await t.run(RunRequest())

        assert result.succeeded
        report: QualityReport = result.outputs["validate"]
        assert report.passed is True

        loaded = await pool.fetch_all(
            "SELECT region, total FROM region_totals ORDER BY region"
        )
        assert loaded == [("EU", 35.0), ("US", 150.0)]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_invalid_input_halts_at_gate_and_skips_load() -> None:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE region_totals ("
            "  region TEXT PRIMARY KEY, "
            "  total  REAL NOT NULL"
            ")"
        )
        t = _build_pipeline(pool=pool, invalid=True)
        result = await t.run(RunRequest())

        report: QualityReport = result.outputs["validate"]
        assert report.passed is False
        # Pandera should have flagged region (ZZ) and amount (-1.0).
        failed_columns = {c.column for c in report.failed_checks}
        assert "region" in failed_columns
        assert "amount" in failed_columns

        outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}
        assert outcomes["validate"] == "ok"          # the assessment ran
        assert outcomes["validate_ok"] == "skipped"  # the gate closed
        assert outcomes["load"] == "skipped"          # the sink never executed

        loaded = await pool.fetch_all("SELECT COUNT(*) FROM region_totals")
        assert loaded == [(0,)]
    finally:
        await pool.close()
