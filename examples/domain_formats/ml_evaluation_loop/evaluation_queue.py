"""``EvaluationQueue`` — the immutable loop state carried through the dynamic DAG.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from examples.domain_formats.ml_evaluation_loop.model_artifact import ModelArtifact
from examples.domain_formats.ml_evaluation_loop.promotion_decision import PromotionDecision


@dataclass(frozen=True)
class EvaluationQueue:
    """Models still to evaluate, plus the decisions taken so far."""

    models: tuple[ModelArtifact, ...]
    model_idx: int = 0
    decisions: tuple[PromotionDecision, ...] = ()

    @property
    def done(self) -> bool:
        return self.model_idx >= len(self.models)

    @property
    def current_model(self) -> ModelArtifact:
        return self.models[self.model_idx]

    def evolve(self, **changes: Any) -> EvaluationQueue:
        """Return a copy of this queue with ``changes`` applied."""
        return replace(self, **changes)

    def evaluator_id(self) -> str:
        """Knot id for the evaluator that will process ``current_model``."""
        model_id = self.current_model.model_id
        return f"eval__{model_id.replace('-', '_')}__{self.model_idx}"
