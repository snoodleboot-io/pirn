"""``RegionMetrics`` — revenue, order and session counts per region.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegionMetrics:
    date: str
    by_region: dict[str, dict]  # region → {revenue, orders, sessions}
