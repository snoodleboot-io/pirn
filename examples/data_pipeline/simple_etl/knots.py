"""Knot factories for the ``examples.data_pipeline.simple_etl`` example."""

from __future__ import annotations

import csv
import io
import sqlite3

from pirn.core.knot_factory import KnotFactory

from examples.data_pipeline.simple_etl.clean_dataset import CleanDataset
from examples.data_pipeline.simple_etl.enriched_dataset import EnrichedDataset
from examples.data_pipeline.simple_etl.load_result import LoadResult
from examples.data_pipeline.simple_etl.raw_dataset import RawDataset


@KnotFactory.knot
async def extract(source_csv: str) -> RawDataset:
    """Parse CSV text into a list of dicts."""
    reader = csv.DictReader(io.StringIO(source_csv))
    rows = list(reader)
    return RawDataset(rows=rows, source="inline", row_count=len(rows))


@KnotFactory.knot
async def clean(raw: RawDataset, drop_nulls: bool) -> CleanDataset:
    """Drop rows with null values in key columns and normalise types."""
    cleaned = []
    dropped = 0
    for row in raw.rows:
        if drop_nulls and any(v.strip() == "" for v in row.values()):
            dropped += 1
            continue
        cleaned.append(
            {
                "id": int(row["id"]),
                "name": row["name"].strip().title(),
                "amount": float(row["amount"]),
                "region": row["region"].strip().upper(),
            }
        )
    return CleanDataset(rows=cleaned, dropped=dropped, source=raw.source)


@KnotFactory.knot
async def enrich(clean_data: CleanDataset, fx_rate: float) -> EnrichedDataset:
    """Add derived columns: amount_usd and region_group."""
    region_map = {
        "US": "americas",
        "CA": "americas",
        "GB": "emea",
        "DE": "emea",
        "JP": "apac",
    }
    enriched = []
    for row in clean_data.rows:
        enriched.append(
            {
                **row,
                "amount_usd": round(row["amount"] * fx_rate, 2),
                "region_group": region_map.get(row["region"], "other"),
            }
        )
    return EnrichedDataset(rows=enriched, new_columns=["amount_usd", "region_group"])


@KnotFactory.knot
async def load(enriched: EnrichedDataset, db_path: str, table_name: str) -> LoadResult:
    """Write the enriched rows to a SQLite table."""
    conn = sqlite3.connect(db_path)
    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    if enriched.rows:
        cols = ", ".join(enriched.rows[0].keys())
        placeholders = ", ".join("?" for _ in enriched.rows[0])
        conn.execute(f"CREATE TABLE {table_name} ({cols})")
        conn.executemany(
            f"INSERT INTO {table_name} VALUES ({placeholders})",
            [tuple(r.values()) for r in enriched.rows],
        )
    conn.commit()
    conn.close()
    return LoadResult(
        table=table_name, rows_written=len(enriched.rows), db_path=db_path
    )
