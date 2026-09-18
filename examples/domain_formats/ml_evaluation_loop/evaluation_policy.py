"""``EvaluationPolicy`` — the promotion thresholds a candidate model must clear.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import ClassVar


class EvaluationPolicy:
    """Service-level thresholds shared by the metrics stage and the promotion decision."""

    latency_sla_ms: ClassVar[float] = 100.0
    memory_sla_mb: ClassVar[float] = 512.0
    accuracy_threshold: ClassVar[float] = 0.82
