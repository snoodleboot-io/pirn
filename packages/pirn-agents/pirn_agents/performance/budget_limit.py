"""``BudgetLimit`` — which dimension of a :class:`RunBudget` was breached."""

from __future__ import annotations

from enum import Enum


class BudgetLimit(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """The budget dimension a run exhausted.

    String-valued so the member serialises to a stable, human-readable token
    that survives round-trips through the DAG without depending on enum member
    ordering.

    Members
    -------
    ITERATIONS:
        The loop ran more iterations than ``max_iterations`` allowed.
    TOKENS:
        Cumulative token usage exceeded ``max_tokens``.
    DEADLINE:
        Wall-clock elapsed time passed ``deadline_seconds``.
    COST:
        Accrued estimated spend exceeded ``max_cost``.
    """

    ITERATIONS = "iterations"
    TOKENS = "tokens"
    DEADLINE = "deadline"
    COST = "cost"
