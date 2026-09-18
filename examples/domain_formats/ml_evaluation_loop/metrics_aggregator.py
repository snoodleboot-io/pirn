"""``MetricsAggregator`` — folds batch timings and layer structure into metrics.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.ml_evaluation_loop.evaluation_policy import EvaluationPolicy
from examples.domain_formats.ml_evaluation_loop.inference_batch import InferenceBatch
from examples.domain_formats.ml_evaluation_loop.layer_profile import LayerProfile
from examples.domain_formats.ml_evaluation_loop.model_metrics import ModelMetrics
from examples.domain_formats.ml_evaluation_loop.seeded_rng import SeededRng


class MetricsAggregator(Knot):
    """Collect BatchInference + LayerProfiler outputs and compute ModelMetrics."""

    async def process(self, combined: list[Any], **_: Any) -> ModelMetrics:
        batches: list[InferenceBatch] = []
        profile: LayerProfile | None = None

        for item in combined:
            if isinstance(item, list):
                batches = item
            elif isinstance(item, LayerProfile):
                profile = item

        if not batches or profile is None:
            raise ValueError("MetricsAggregator requires both batches and a profile")

        model_id = batches[0].model_id
        all_preds = [p for b in batches for p in b.predictions]
        pred_variance = statistics.variance(all_preds) if len(all_preds) > 1 else 0.0
        # Accuracy proxy: low variance around 0.5 suggests confident binary predictions
        accuracy = max(0.0, min(1.0, 1.0 - (pred_variance * 4.0)))

        # F1 proxy: accuracy ± small random perturbation seeded from model_id
        rng = SeededRng.for_model(model_id, "f1")
        f1 = max(0.0, min(1.0, accuracy + rng.uniform(-0.05, 0.05)))

        latencies = [b.latency_ms for b in batches]
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted)
        p99_idx = max(0, math.ceil(0.99 * len(latencies_sorted)) - 1)
        p99 = latencies_sorted[p99_idx]

        return ModelMetrics(
            model_id=model_id,
            accuracy=accuracy,
            f1=f1,
            latency_p50_ms=p50,
            latency_p99_ms=p99,
            memory_mb=profile.memory_mb,
            passes_latency_sla=p99 < EvaluationPolicy.latency_sla_ms,
            passes_memory_sla=profile.memory_mb < EvaluationPolicy.memory_sla_mb,
        )
