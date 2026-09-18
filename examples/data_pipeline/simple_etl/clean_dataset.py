"""``CleanDataset``

Part of the ``examples.data_pipeline.simple_etl`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CleanDataset:
    rows: list[dict]
    dropped: int
    source: str
