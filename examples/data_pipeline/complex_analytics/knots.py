"""Knot factories for the ``examples.data_pipeline.complex_analytics`` example."""

from __future__ import annotations

import asyncio
import random

from pirn.core.knot_factory import KnotFactory

from examples.data_pipeline.complex_analytics.cohort_metrics import CohortMetrics
from examples.data_pipeline.complex_analytics.daily_report import DailyReport
from examples.data_pipeline.complex_analytics.events_snapshot import EventsSnapshot
from examples.data_pipeline.complex_analytics.joined_dataset import JoinedDataset
from examples.data_pipeline.complex_analytics.orders_snapshot import OrdersSnapshot
from examples.data_pipeline.complex_analytics.region_metrics import RegionMetrics
from examples.data_pipeline.complex_analytics.users_snapshot import UsersSnapshot


@KnotFactory.knot
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


@KnotFactory.knot
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


@KnotFactory.knot
async def ingest_users(run_date: str, seed: int) -> UsersSnapshot:
    """Fetch user activity counts from the user service."""
    await asyncio.sleep(0.01)
    rng = random.Random(seed + 2000)
    return UsersSnapshot(
        date=run_date,
        active_users=rng.randint(800, 1200),
        new_users=rng.randint(20, 80),
    )


@KnotFactory.knot
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


@KnotFactory.knot
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


@KnotFactory.knot
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


@KnotFactory.knot
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
