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
    uv run python examples/data_pipeline/complex_analytics.py
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

# ----------------------------------------------------------------- models


@dataclass
class OrdersSnapshot:
    date: str
    rows: list[dict]

    @property
    def revenue(self) -> float:
        return sum(r["amount"] for r in self.rows)


@dataclass
class EventsSnapshot:
    date: str
    rows: list[dict]

    @property
    def session_count(self) -> int:
        return len({r["session_id"] for r in self.rows})


@dataclass
class UsersSnapshot:
    date: str
    active_users: int
    new_users: int


@dataclass
class JoinedDataset:
    date: str
    order_rows: list[dict]
    event_rows: list[dict]
    active_users: int


@dataclass
class RegionMetrics:
    date: str
    by_region: dict[str, dict]  # region → {revenue, orders, sessions}


@dataclass
class CohortMetrics:
    date: str
    by_cohort: dict[str, dict]  # cohort → {revenue, retention}


@dataclass
class DailyReport:
    date: str
    total_revenue: float
    total_orders: int
    active_users: int
    top_region: str
    region_metrics: dict
    cohort_metrics: dict


# ----------------------------------------------------------------- knots


@knot
async def ingest_orders(run_date: str, seed: int) -> OrdersSnapshot:
    """Fetch orders from the transactional database."""
    await asyncio.sleep(0.02)  # simulate DB query
    rng = random.Random(seed)
    regions = ["US", "GB", "DE", "JP", "CA"]
    rows = [
        {
            "order_id": f"ord_{i:04d}",
            "region": rng.choice(regions),
            "amount": round(rng.uniform(10, 500), 2),
            "cohort": f"cohort_{rng.randint(1, 5)}",
        }
        for i in range(rng.randint(80, 120))
    ]
    return OrdersSnapshot(date=run_date, rows=rows)


@knot
async def ingest_events(run_date: str, seed: int) -> EventsSnapshot:
    """Fetch clickstream events from the analytics store."""
    await asyncio.sleep(0.015)
    rng = random.Random(seed + 1000)
    rows = [
        {
            "event_id": f"ev_{i:04d}",
            "session_id": f"s_{rng.randint(1, 200)}",
            "event_type": rng.choice(["view", "click", "purchase"]),
        }
        for i in range(rng.randint(400, 600))
    ]
    return EventsSnapshot(date=run_date, rows=rows)


@knot
async def ingest_users(run_date: str, seed: int) -> UsersSnapshot:
    """Fetch user activity counts from the user service."""
    await asyncio.sleep(0.01)
    rng = random.Random(seed + 2000)
    return UsersSnapshot(
        date=run_date,
        active_users=rng.randint(800, 1200),
        new_users=rng.randint(20, 80),
    )


@knot
async def join_datasets(
    orders: OrdersSnapshot,
    events: EventsSnapshot,
    users: UsersSnapshot,
) -> JoinedDataset:
    """Combine the three snapshots into a single joined dataset."""
    return JoinedDataset(
        date=orders.date,
        order_rows=orders.rows,
        event_rows=events.rows,
        active_users=users.active_users,
    )


@knot
async def aggregate_by_region(joined: JoinedDataset) -> RegionMetrics:
    """Compute per-region revenue, order count, and session count."""
    by_region: dict[str, dict] = {}
    for row in joined.order_rows:
        r = by_region.setdefault(row["region"], {"revenue": 0.0, "orders": 0})
        r["revenue"] += row["amount"]
        r["orders"] += 1
    # Attach session counts (simplified: split evenly)
    sessions = len({r["session_id"] for r in joined.event_rows})
    per_region = max(1, sessions // max(1, len(by_region)))
    for r in by_region.values():
        r["sessions"] = per_region
    return RegionMetrics(date=joined.date, by_region=by_region)


@knot
async def aggregate_by_cohort(joined: JoinedDataset) -> CohortMetrics:
    """Compute per-cohort revenue and retention."""
    by_cohort: dict[str, dict] = {}
    for row in joined.order_rows:
        c = by_cohort.setdefault(row["cohort"], {"revenue": 0.0, "orders": 0})
        c["revenue"] += row["amount"]
        c["orders"] += 1
    total = sum(c["orders"] for c in by_cohort.values()) or 1
    for c in by_cohort.values():
        c["retention"] = round(c["orders"] / total, 3)
    return CohortMetrics(date=joined.date, by_cohort=by_cohort)


@knot
async def build_report(
    region_metrics: RegionMetrics,
    cohort_metrics: CohortMetrics,
    joined: JoinedDataset,
) -> DailyReport:
    """Merge metrics into the final daily report."""
    top_region = max(
        region_metrics.by_region,
        key=lambda r: region_metrics.by_region[r]["revenue"],
        default="N/A",
    )
    total_revenue = sum(r["revenue"] for r in region_metrics.by_region.values())
    total_orders = sum(r["orders"] for r in region_metrics.by_region.values())
    return DailyReport(
        date=region_metrics.date,
        total_revenue=round(total_revenue, 2),
        total_orders=total_orders,
        active_users=joined.active_users,
        top_region=top_region,
        region_metrics=region_metrics.by_region,
        cohort_metrics=cohort_metrics.by_cohort,
    )


# ----------------------------------------------------------------- wiring


def build_tapestry(history=None) -> Tapestry:
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


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    today = date.today()
    for days_ago in [2, 1, 0]:
        run_date = (today - timedelta(days=days_ago)).isoformat()
        result = await t.run(RunRequest(parameters={"run_date": run_date, "seed": days_ago * 42}))
        report: DailyReport = result.outputs["report"]
        print(
            f"{report.date}  revenue=${report.total_revenue:>10,.2f}  "
            f"orders={report.total_orders:>4}  users={report.active_users:>5}  "
            f"top={report.top_region}"
        )


if __name__ == "__main__":
    asyncio.run(main())
