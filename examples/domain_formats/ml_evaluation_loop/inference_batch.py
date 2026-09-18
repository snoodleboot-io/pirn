"""``InferenceBatch`` — one synthetic inference batch and its timings.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceBatch:
    """Predictions and latency for one batch run against a model."""

    model_id: str
    batch_id: int
    predictions: tuple[float, ...]
    latency_ms: float
    throughput_samples_per_sec: float
