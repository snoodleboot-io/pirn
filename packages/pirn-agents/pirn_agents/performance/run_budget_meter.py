"""``RunBudgetMeter`` — the mutable accountant that enforces a :class:`RunBudget`.

One meter is created per run and threaded through the loop/pattern. It holds
the immutable :class:`RunBudget` alongside live counters and a monotonic start
stamp; callers ``spend_iteration`` / ``spend_tokens`` and ``checkpoint`` at
loop boundaries. On the first breach the meter cancels its shared
:class:`~pirn_agents.performance.cancellation_token.CancellationToken` (so any
in-flight cooperating tasks unwind cleanly) *and* raises the typed
:class:`~pirn_agents.performance.budget_breach_error.BudgetBreachError` — the
loop catches it and returns a clean terminal result rather than leaking a
half-updated state.

This is the single shared enforcement path the ADR calls for: F7/F8/F9 loops
each accept an optional ``RunBudgetMeter`` (or build one from a ``RunBudget``)
and call the same ``spend_*``/``checkpoint`` methods, so budget semantics never
diverge between patterns.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.cancellation_token import CancellationToken
from pirn_agents.performance.run_budget import RunBudget


class RunBudgetMeter:
    """Live accounting for one run against a fixed :class:`RunBudget`."""

    def __init__(
        self,
        budget: RunBudget,
        *,
        token: CancellationToken | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Bind a budget to fresh counters and a cancellation token.

        Args:
            budget: The immutable limits to enforce.
            token: Cancellation token to flip on breach; a fresh one is created
                when omitted. Pass a shared token to fan a breach out to
                sibling tasks.
            monotonic: Clock source for deadline accounting, injectable so
                deadline breaches are deterministic under test.

        Raises:
            TypeError: If ``budget`` is not a :class:`RunBudget`.
        """
        if not isinstance(budget, RunBudget):
            raise TypeError(
                f"RunBudgetMeter: budget must be a RunBudget, got {type(budget).__name__}"
            )
        self._budget = budget
        self._token = token if token is not None else CancellationToken()
        self._monotonic = monotonic
        self._start = monotonic()
        self._iterations = 0
        self._tokens = 0

    @property
    def budget(self) -> RunBudget:
        """The immutable budget being enforced."""
        return self._budget

    @property
    def token(self) -> CancellationToken:
        """The cancellation token flipped on breach."""
        return self._token

    @property
    def iterations(self) -> int:
        """Iterations spent so far."""
        return self._iterations

    @property
    def tokens(self) -> int:
        """Tokens spent so far."""
        return self._tokens

    @property
    def elapsed(self) -> float:
        """Wall-clock seconds since the meter was created."""
        return self._monotonic() - self._start

    def spend_iteration(self, count: int = 1) -> None:
        """Record ``count`` iterations, then re-check every budget dimension."""
        self._iterations += count
        self._checkpoint()

    def spend_tokens(self, count: int) -> None:
        """Record ``count`` tokens, then re-check every budget dimension."""
        self._tokens += count
        self._checkpoint()

    def checkpoint(self) -> None:
        """Re-check every budget dimension without spending anything.

        Use at the top of a loop body to catch a deadline breach even on an
        iteration that consumes no new tokens.
        """
        self._checkpoint()

    def _checkpoint(self) -> None:
        """Enforce all three dimensions; on breach cancel the token and raise.

        The token is cancelled *before* the exception propagates so a shared
        token wakes sibling tasks in the same tick the breach is raised.
        """
        try:
            self._budget.check_iterations(self._iterations)
            self._budget.check_tokens(self._tokens)
            self._budget.check_deadline(self.elapsed)
        except BudgetBreachError as exc:
            self._token.cancel(reason=str(exc))
            raise
