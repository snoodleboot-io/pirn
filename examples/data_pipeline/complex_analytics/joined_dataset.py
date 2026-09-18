"""``JoinedDataset`` — the three daily snapshots combined into one dataset.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JoinedDataset:
    date: str
    order_rows: list[dict]
    event_rows: list[dict]
    active_users: int
