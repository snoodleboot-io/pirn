"""``RawBatch`` — CSV rows as parsed, before scoring.

Part of the ``examples.data_pipeline.transport_layers`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawBatch:
    rows: list[dict[str, str]]
    row_count: int
