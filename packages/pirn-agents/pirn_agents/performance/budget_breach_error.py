"""``BudgetBreachError`` — typed exception raised when a :class:`RunBudget` is exhausted."""

from __future__ import annotations

from pirn_agents.performance.budget_limit import BudgetLimit


class BudgetBreachError(RuntimeError):
    """Raised the instant a run exceeds one dimension of its :class:`RunBudget`.

    A *typed* breach (rather than a bare ``RuntimeError`` or an uncaught
    arithmetic error) so loop callers can catch exactly this and convert it into
    a clean terminal result. Carries the breached :class:`BudgetLimit` plus the
    amount spent and the amount allowed for diagnostics.

    Attributes
    ----------
    limit:
        Which budget dimension was exhausted.
    spent:
        The measured amount consumed at breach time (iterations, tokens, or
        elapsed seconds, depending on ``limit``).
    allowed:
        The configured cap that ``spent`` exceeded.
    """

    def __init__(self, limit: BudgetLimit, *, spent: float, allowed: float) -> None:
        self.limit = limit
        self.spent = spent
        self.allowed = allowed
        super().__init__(
            f"RunBudget exhausted: {limit.value} spent={spent} exceeds allowed={allowed}"
        )
