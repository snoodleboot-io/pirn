"""``_RegistryReport`` — the terminal knot of the registry sweep.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot

from examples.domain_formats.ml_evaluation_loop.evaluation_queue import EvaluationQueue
from examples.domain_formats.ml_evaluation_loop.evaluation_report import EvaluationReport


class _RegistryReport(Knot):
    """Terminal knot — surfaces the final EvaluationReport."""

    async def process(self, queue: EvaluationQueue, **_: Any) -> EvaluationReport:
        promoted = [d.model_id for d in queue.decisions if d.promoted]
        rejected = [d.model_id for d in queue.decisions if not d.promoted]
        return EvaluationReport(
            n_models=len(queue.decisions),
            promoted=promoted,
            rejected=rejected,
            decisions=queue.decisions,
        )
