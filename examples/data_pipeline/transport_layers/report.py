"""``Report`` — high/low value counts for one scored batch.

Part of the ``examples.data_pipeline.transport_layers`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Report:
    high_value_count: int
    low_value_count: int
    mean_score: float
