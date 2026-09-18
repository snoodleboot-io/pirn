"""``ScoredBatch`` — rows with a normalised score attached.

Part of the ``examples.data_pipeline.transport_layers`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoredBatch:
    rows: list[dict]
    mean_score: float
