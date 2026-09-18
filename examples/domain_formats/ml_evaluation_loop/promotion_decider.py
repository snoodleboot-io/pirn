"""``PromotionDecider`` — promotes or rejects a model, then advances the sweep.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.domain_formats.ml_evaluation_loop.evaluation_policy import EvaluationPolicy
from examples.domain_formats.ml_evaluation_loop.evaluation_queue import EvaluationQueue
from examples.domain_formats.ml_evaluation_loop.model_metrics import ModelMetrics
from examples.domain_formats.ml_evaluation_loop.promotion_decision import PromotionDecision
from examples.domain_formats.ml_evaluation_loop.registry_ids import RegistryIds
from examples.domain_formats.ml_evaluation_loop.registry_report import _RegistryReport


class PromotionDecider(Knot):
    """Decide promote/reject; register next ModelEvaluator or _RegistryReport."""

    async def process(
        self,
        metrics: ModelMetrics,
        queue: EvaluationQueue,
        **_: Any,
    ) -> PromotionDecision:
        reasons: list[str] = []
        if metrics.accuracy < EvaluationPolicy.accuracy_threshold:
            reasons.append(
                f"accuracy {metrics.accuracy:.3f} < {EvaluationPolicy.accuracy_threshold}"
            )
        if not metrics.passes_latency_sla:
            reasons.append(
                f"p99 latency {metrics.latency_p99_ms:.1f}ms "
                f">= {EvaluationPolicy.latency_sla_ms}ms SLA"
            )
        if not metrics.passes_memory_sla:
            reasons.append(
                f"memory {metrics.memory_mb:.1f}MB >= {EvaluationPolicy.memory_sla_mb}MB SLA"
            )

        promoted = len(reasons) == 0
        reason = "all thresholds met" if promoted else "; ".join(reasons)

        decision = PromotionDecision(
            model_id=metrics.model_id,
            promoted=promoted,
            reason=reason,
            metrics=metrics,
        )

        new_decisions = (*queue.decisions, decision)
        new_queue = queue.evolve(
            model_idx=queue.model_idx + 1,
            decisions=new_decisions,
        )

        store = Tapestry.current_store()
        if store is None:
            return decision

        if not new_queue.done:
            # Imported here, not at module scope: ModelEvaluator registers this
            # decider and this decider registers the next evaluator, so the two
            # modules refer to each other.
            from examples.domain_formats.ml_evaluation_loop.model_evaluator import ModelEvaluator

            next_evaluator = ModelEvaluator(
                queue=new_queue,
                _config=KnotConfig(id=new_queue.evaluator_id(), validate_io=False),
            )
            store.register(next_evaluator)
        else:
            store.register(
                _RegistryReport(
                    queue=new_queue,
                    _config=KnotConfig(id=RegistryIds.complete, validate_io=False),
                )
            )

        return decision
