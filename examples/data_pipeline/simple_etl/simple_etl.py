"""Example: Simple ETL pipeline — extract, transform, load.

Reads CSV data, cleans and enriches it, then writes to a SQLite database.
Demonstrates pirn's content-addressed caching: re-running with the same
source file skips knots whose inputs haven't changed.

Run with:
    uv run python -m examples.data_pipeline.simple_etl
"""

from __future__ import annotations

from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.data_pipeline.simple_etl.knots import clean, enrich, extract, load


class SimpleEtl:
    """Builds and runs the simple ETL tapestry three times to show caching."""

    sample_csv = """\
id,name,amount,region
1,alice smith,1200.50,US
2,bob jones,,GB
3,carol white,850.00,DE
4,dave brown,2100.75,JP
5,eve black,950.00,CA
6,,600.00,US
"""

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire extract -> clean -> enrich -> load behind five parameters."""
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

    @classmethod
    def _parameters(cls, fx_rate: float) -> dict[str, object]:
        return {
            "source_csv": cls.sample_csv,
            "drop_nulls": True,
            "fx_rate": fx_rate,
            "db_path": ":memory:",
            "table_name": "sales",
        }

    @classmethod
    async def main(cls) -> None:
        """Run the pipeline, re-run it cached, then re-run with a new FX rate."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        print("Run 1 — full pipeline")
        result = await t.run(RunRequest(parameters=cls._parameters(fx_rate=1.08)))
        load_result = result.outputs["load"]
        print(f"  Loaded {load_result.rows_written} rows into '{load_result.table}'")
        for rec in result.lineage:
            print(f"  {rec.knot_id:<12} outcome={rec.outcome}")

        print("\nRun 2 — same inputs, all knots should be cached (skipped)")
        result2 = await t.run(RunRequest(parameters=cls._parameters(fx_rate=1.08)))
        for rec in result2.lineage:
            print(f"  {rec.knot_id:<12} outcome={rec.outcome}")

        print("\nRun 3 — new FX rate, only enrich+load re-run")
        result3 = await t.run(RunRequest(parameters=cls._parameters(fx_rate=1.12)))
        for rec in result3.lineage:
            print(f"  {rec.knot_id:<12} outcome={rec.outcome}")
