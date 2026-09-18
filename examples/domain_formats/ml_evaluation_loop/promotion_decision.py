"""``PromotionDecision`` — promote or reject, and why.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.ml_evaluation_loop.model_metrics import ModelMetrics


@dataclass(frozen=True)
class PromotionDecision:
    """One model's promote/reject verdict and the metrics it rests on."""

    model_id: str
    promoted: bool
    reason: str
    metrics: ModelMetrics
