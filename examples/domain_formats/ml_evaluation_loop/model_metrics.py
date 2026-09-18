"""``ModelMetrics`` — the quality and serving metrics one model was measured at.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelMetrics:
    """Quality plus serving metrics, with the SLA verdicts already applied."""

    model_id: str
    accuracy: float
    f1: float
    latency_p50_ms: float
    latency_p99_ms: float
    memory_mb: float
    passes_latency_sla: bool
    passes_memory_sla: bool
