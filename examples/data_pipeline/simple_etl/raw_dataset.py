"""``RawDataset``

Part of the ``examples.data_pipeline.simple_etl`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawDataset:
    rows: list[dict[str, str]]
    source: str
    row_count: int
