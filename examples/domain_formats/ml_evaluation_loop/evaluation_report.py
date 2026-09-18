"""``EvaluationReport`` — the run's final summary of the registry sweep.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.domain_formats.ml_evaluation_loop.promotion_decision import PromotionDecision


@dataclass(frozen=True)
class EvaluationReport:
    """Which models were promoted, which rejected, and every decision in order."""

    n_models: int
    promoted: list[str]
    rejected: list[str]
    decisions: tuple[PromotionDecision, ...]
