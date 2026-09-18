"""``CohortMetrics`` — revenue and retention per cohort.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CohortMetrics:
    date: str
    by_cohort: dict[str, dict]  # cohort → {revenue, retention}
