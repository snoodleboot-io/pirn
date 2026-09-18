"""``DailyReport`` — the merged daily business metrics report.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DailyReport:
    date: str
    total_revenue: float
    total_orders: int
    active_users: int
    top_region: str
    region_metrics: dict
    cohort_metrics: dict
