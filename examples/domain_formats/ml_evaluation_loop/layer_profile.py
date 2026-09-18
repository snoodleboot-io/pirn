"""``LayerProfile`` — a model's parameter, memory and FLOP footprint.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerProfile:
    """Static structure of a model, derived from its tensor shapes alone."""

    model_id: str
    total_params: int
    layer_count: int
    memory_mb: float
    compute_ops_per_sample: int
