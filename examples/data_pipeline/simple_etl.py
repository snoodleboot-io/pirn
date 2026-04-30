"""Example: Simple ETL pipeline — extract, transform, load.

Reads CSV data, cleans and enriches it, then writes to a SQLite database.
Demonstrates pirn's content-addressed caching: re-running with the same
source file skips knots whose inputs haven't changed.

Run with:
    uv run python examples/data_pipeline/simple_etl.py
"""

import asyncio
import csv
import io
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class RawDataset:
    rows: list[dict[str, str]]
    source: str
    row_count: int


@dataclass
class CleanDataset:
    rows: list[dict]
    dropped: int
    source: str


@dataclass
class EnrichedDataset:
    rows: list[dict]
    new_columns: list[str]


@dataclass
class LoadResult:
    table: str
    rows_written: int
    db_path: str


# ----------------------------------------------------------------- knots


@knot
async def extract(source_csv: str) -> RawDataset:
    """Parse CSV text into a list of dicts."""
    reader = csv.DictReader(io.StringIO(source_csv))
    rows = list(reader)
    return RawDataset(rows=rows, source="inline", row_count=len(rows))


@knot
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


@knot
async def enrich(clean_data: CleanDataset, fx_rate: float) -> EnrichedDataset:
    """Add derived columns: amount_usd and region_group."""
    region_map = {"US": "americas", "CA": "americas", "GB": "emea", "DE": "emea", "JP": "apac"}
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


@knot
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
    return LoadResult(table=table_name, rows_written=len(enriched.rows), db_path=db_path)


# ----------------------------------------------------------------- wiring


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        source_csv = Parameter("source_csv", str, _config=KnotConfig(id="source_csv"))
        drop_nulls = Parameter("drop_nulls", bool, _config=KnotConfig(id="drop_nulls"))
        fx_rate = Parameter("fx_rate", float, _config=KnotConfig(id="fx_rate"))
        db_path = Parameter("db_path", str, _config=KnotConfig(id="db_path"))
        table_name = Parameter("table_name", str, _config=KnotConfig(id="table_name"))

        raw = extract(source_csv=source_csv, _config=KnotConfig(id="extract"))
        cleaned = clean(raw=raw, drop_nulls=drop_nulls, _config=KnotConfig(id="clean"))
        enriched = enrich(clean_data=cleaned, fx_rate=fx_rate, _config=KnotConfig(id="enrich"))
        load(
            enriched=enriched,
            db_path=db_path,
            table_name=table_name,
            _config=KnotConfig(id="load"),
        )
    return t


# ----------------------------------------------------------------- main

SAMPLE_CSV = """\
id,name,amount,region
1,alice smith,1200.50,US
2,bob jones,,GB
3,carol white,850.00,DE
4,dave brown,2100.75,JP
5,eve black,950.00,CA
6,,600.00,US
"""


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    print("Run 1 — full pipeline")
    result = await t.run(
        RunRequest(
            parameters={
                "source_csv": SAMPLE_CSV,
                "drop_nulls": True,
                "fx_rate": 1.08,
                "db_path": ":memory:",
                "table_name": "sales",
            }
        )
    )
    load_result = result.outputs["load"]
    print(f"  Loaded {load_result.rows_written} rows into '{load_result.table}'")
    for rec in result.lineage:
        print(f"  {rec.knot_id:<12} outcome={rec.outcome}")

    print("\nRun 2 — same inputs, all knots should be cached (skipped)")
    result2 = await t.run(
        RunRequest(
            parameters={
                "source_csv": SAMPLE_CSV,
                "drop_nulls": True,
                "fx_rate": 1.08,
                "db_path": ":memory:",
                "table_name": "sales",
            }
        )
    )
    for rec in result2.lineage:
        print(f"  {rec.knot_id:<12} outcome={rec.outcome}")

    print("\nRun 3 — new FX rate, only enrich+load re-run")
    result3 = await t.run(
        RunRequest(
            parameters={
                "source_csv": SAMPLE_CSV,
                "drop_nulls": True,
                "fx_rate": 1.12,  # changed
                "db_path": ":memory:",
                "table_name": "sales",
            }
        )
    )
    for rec in result3.lineage:
        print(f"  {rec.knot_id:<12} outcome={rec.outcome}")


if __name__ == "__main__":
    asyncio.run(main())
