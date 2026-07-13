"""``SpendCapPolicy`` — what a run does when it would exceed its cost ceiling."""

from __future__ import annotations

from enum import Enum


class SpendCapPolicy(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """The action taken when the next call would breach a :class:`RunBudget` cost cap.

    String-valued so the member serialises to a stable, human-readable token that
    survives round-trips through the DAG without depending on enum ordering.

    Members
    -------
    ABORT:
        Stop the run by raising a
        :class:`~pirn_agents.performance.budget_breach_error.BudgetBreachError`.
    DOWNSHIFT:
        Stay on (or fall back to) the cheaper option rather than spending more —
        e.g. do not escalate a model cascade to a pricier tier.
    """

    ABORT = "abort"
    DOWNSHIFT = "downshift"
