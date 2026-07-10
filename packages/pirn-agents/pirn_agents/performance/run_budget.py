"""``RunBudget`` — an immutable iteration/token/wall-clock budget for a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.budget_limit import BudgetLimit


@dataclass(frozen=True)
class RunBudget(PirnOpaqueValue):
    """A frozen cap on how much work a loop or pattern may consume.

    Each dimension is independently optional — ``None`` means "unbounded on
    this axis". The type is a pure value: it holds *limits*, not counters, so
    it hash-equals naturally for content addressing. The mutable accounting
    (spending iterations/tokens and comparing against the wall clock) lives in
    :class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter`, which
    threads one shared budget through a run.

    The ``check_*`` methods are pure predicates that raise a typed
    :class:`BudgetBreachError` when a measured amount exceeds the cap, so every
    caller enforces a breach the same way.

    Attributes
    ----------
    max_iterations:
        Maximum loop iterations, or ``None`` for unbounded.
    max_tokens:
        Maximum cumulative token usage, or ``None`` for unbounded.
    deadline_seconds:
        Maximum wall-clock elapsed time in seconds, or ``None`` for unbounded.
    """

    max_iterations: int | None = None
    max_tokens: int | None = None
    deadline_seconds: float | None = None

    def __post_init__(self) -> None:
        """Validate every supplied dimension is a non-negative number.

        ``bool`` is rejected for the integer fields because ``True``/``False``
        are ``int`` subclasses and a boolean budget is always a mistake.
        """
        for name, value in (
            ("max_iterations", self.max_iterations),
            ("max_tokens", self.max_tokens),
        ):
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(
                    f"RunBudget: {name} must be a non-negative int or None, got {value!r}"
                )
        deadline = self.deadline_seconds
        if deadline is not None and (
            isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or deadline < 0
        ):
            raise ValueError(
                f"RunBudget: deadline_seconds must be a non-negative number or None, "
                f"got {deadline!r}"
            )

    def check_iterations(self, spent: int) -> None:
        """Raise :class:`BudgetBreachError` if ``spent`` exceeds ``max_iterations``."""
        if self.max_iterations is not None and spent > self.max_iterations:
            raise BudgetBreachError(
                BudgetLimit.ITERATIONS, spent=spent, allowed=self.max_iterations
            )

    def check_tokens(self, spent: int) -> None:
        """Raise :class:`BudgetBreachError` if ``spent`` exceeds ``max_tokens``."""
        if self.max_tokens is not None and spent > self.max_tokens:
            raise BudgetBreachError(BudgetLimit.TOKENS, spent=spent, allowed=self.max_tokens)

    def check_deadline(self, elapsed: float) -> None:
        """Raise :class:`BudgetBreachError` if ``elapsed`` exceeds ``deadline_seconds``."""
        if self.deadline_seconds is not None and elapsed > self.deadline_seconds:
            raise BudgetBreachError(
                BudgetLimit.DEADLINE, spent=elapsed, allowed=self.deadline_seconds
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "deadline_seconds": self.deadline_seconds,
        }
