"""``EnrichedDataset``

Part of the ``examples.data_pipeline.simple_etl`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnrichedDataset:
    rows: list[dict]
    new_columns: list[str]
