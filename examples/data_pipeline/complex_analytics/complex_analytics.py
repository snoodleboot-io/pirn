"""Example: Complex analytics pipeline with multiple data sources and aggregation.

Models a daily business metrics pipeline:
  ingest (orders + events + users in parallel)
    → join → aggregate by region → aggregate by cohort (parallel)
    → merge_metrics → report

Demonstrates:
- True parallel I/O across three data sources
- Multi-parent aggregation (Aggregator node)
- Content-addressed result caching across daily runs
- Postgres-backed lineage for query-by-output-hash

Run with:
    uv run python -m examples.data_pipeline.complex_analytics
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from examples.data_pipeline.complex_analytics.daily_report import DailyReport
from examples.data_pipeline.complex_analytics.knots import (
    aggregate_by_cohort,
    aggregate_by_region,
    build_report,
    ingest_events,
    ingest_orders,
    ingest_users,
    join_datasets,
)


class ComplexAnalytics:
    """Builds and runs the daily analytics tapestry for three consecutive days."""

    _days_ago: ClassVar[tuple[int, ...]] = (2, 1, 0)
    _seed_step: ClassVar[int] = 42

    @staticmethod
    def build_tapestry(history: SQLiteHistory | None = None) -> Tapestry:
        """Wire ingest (x3) → join → region/cohort aggregation → report."""
        with Tapestry(history=history) as t:
            run_date = Parameter("run_date", str, _config=KnotConfig(id="run_date"))
            seed = Parameter("seed", int, _config=KnotConfig(id="seed"))

            orders = ingest_orders(run_date=run_date, seed=seed, _config=KnotConfig(id="orders"))
            events = ingest_events(run_date=run_date, seed=seed, _config=KnotConfig(id="events"))
            users = ingest_users(run_date=run_date, seed=seed, _config=KnotConfig(id="users"))
            joined = join_datasets(
                orders=orders, events=events, users=users, _config=KnotConfig(id="join")
            )
            regions = aggregate_by_region(joined=joined, _config=KnotConfig(id="regions"))
            cohorts = aggregate_by_cohort(joined=joined, _config=KnotConfig(id="cohorts"))
            build_report(
                region_metrics=regions,
                cohort_metrics=cohorts,
                joined=joined,
                _config=KnotConfig(id="report"),
            )
        return t

    @classmethod
    async def main(cls) -> None:
        """Run the pipeline once per day and print each daily report line."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        t = cls.build_tapestry(history=history)

        today = date.today()
        for days_ago in cls._days_ago:
            run_date = (today - timedelta(days=days_ago)).isoformat()
            result = await t.run(
                RunRequest(parameters={"run_date": run_date, "seed": days_ago * cls._seed_step})
            )
            report: DailyReport = result.outputs["report"]
            print(
                f"{report.date}  revenue=${report.total_revenue:>10,.2f}  "
                f"orders={report.total_orders:>4}  users={report.active_users:>5}  "
                f"top={report.top_region}"
            )
