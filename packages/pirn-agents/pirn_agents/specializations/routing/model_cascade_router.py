"""``ModelCascadeRouter`` — try a cheap model first, escalate only when needed.

Cost-first routing: tiers are supplied cheapest-first and the router invokes them
in order, stopping at the first output whose confidence clears that tier's floor.
It escalates to a pricier tier only on **low confidence** or a **tier failure**,
so the bulk of traffic is served by the cheap model while hard cases still reach
a stronger one. Every decision is recorded on the returned
:class:`~pirn_agents.specializations.routing.cascade_outcome.CascadeOutcome` for
cost analysis.

The confidence check is injected (F12's eval signals plug in here as a stub in
tests) and the tiers carry their own provider callables, so the cascade is
provider-neutral — no vendor is privileged and none is imported. When a
:class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` is supplied the
router accrues each tier's estimated cost and honours a
:class:`~pirn_agents.performance.spend_cap_policy.SpendCapPolicy`: it either
aborts or downshifts (declines to escalate to the pricier tier) before blowing
the spend cap.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class ModelCascadeRouter:
    """Route to cost-ordered model tiers, escalating on low confidence or failure."""

    def __init__(
        self,
        tiers: Sequence[CascadeTier],
        confidence: Callable[[Any], Awaitable[float]],
        *,
        meter: RunBudgetMeter | None = None,
        spend_cap_policy: SpendCapPolicy = SpendCapPolicy.DOWNSHIFT,
    ) -> None:
        """Create a cascade over ``tiers`` (cheapest first).

        Args:
            tiers: The model tiers to try in order; must be non-empty and each a
                :class:`CascadeTier`.
            confidence: Async scorer mapping a tier's output to a confidence in
                ``[0, 1]`` — the pluggable escalation trigger.
            meter: Optional budget meter; when present each tier's estimated cost
                accrues into it and the spend cap is enforced.
            spend_cap_policy: What to do when escalating would breach the cost
                cap — abort the run or downshift (stop escalating).

        Raises:
            ValueError: If ``tiers`` is empty.
            TypeError: If any tier is not a :class:`CascadeTier` or ``confidence``
                is not callable.
        """
        tier_tuple = tuple(tiers)
        if not tier_tuple:
            raise ValueError("ModelCascadeRouter: tiers must be non-empty")
        for index, tier in enumerate(tier_tuple):
            if not isinstance(tier, CascadeTier):
                raise TypeError(
                    f"ModelCascadeRouter: tiers[{index}] must be a CascadeTier, got "
                    f"{type(tier).__name__}"
                )
        if not callable(confidence):
            raise TypeError("ModelCascadeRouter: confidence must be an async callable")
        self._tiers = tier_tuple
        self._confidence = confidence
        self._meter = meter
        self._policy = spend_cap_policy

    async def route(self, request: Any) -> CascadeOutcome:
        """Run the cascade for ``request`` and return the observable outcome.

        Walks the tiers cheapest-first: on a tier failure or a sub-floor
        confidence it escalates; on the first accepted output it returns
        immediately. If a supplied meter reports that the next tier would breach
        the spend cap, the configured :class:`SpendCapPolicy` decides between
        aborting and downshifting.

        Args:
            request: The payload passed unchanged to each tier's ``invoke``.

        Returns:
            A :class:`CascadeOutcome` carrying the value, the chosen tier, and the
            full decision log.

        Raises:
            pirn_agents.performance.budget_breach_error.BudgetBreachError: When
                the spend cap is exceeded under an ``ABORT`` policy (or the
                cheapest tier alone is unaffordable).
        """
        attempted: list[str] = []
        decisions: list[str] = []
        best_value: Any = None
        best_tier: str | None = None
        best_confidence: float | None = None

        for index, tier in enumerate(self._tiers):
            downshift = self._guard_spend_cap(tier, index, decisions)
            if downshift:
                return self._best_outcome(
                    best_value, best_tier, best_confidence, attempted, decisions
                )

            attempted.append(tier.name)
            try:
                value = await tier.invoke(request)
            except Exception as exc:
                decisions.append(f"{tier.name}: failed ({exc}) -> escalate")
                continue

            if self._meter is not None:
                self._meter.spend_cost(tier.estimated_cost)

            score = float(await self._confidence(value))
            if score >= tier.min_confidence:
                decisions.append(f"{tier.name}: accepted (confidence={score})")
                return CascadeOutcome(
                    value=value,
                    chosen=tier.name,
                    succeeded=True,
                    escalated=index > 0,
                    attempted=tuple(attempted),
                    decisions=tuple(decisions),
                    confidence=score,
                )
            decisions.append(f"{tier.name}: low confidence={score} -> escalate")
            best_value, best_tier, best_confidence = value, tier.name, score

        return self._best_outcome(best_value, best_tier, best_confidence, attempted, decisions)

    def _guard_spend_cap(self, tier: CascadeTier, index: int, decisions: list[str]) -> bool:
        """Enforce the spend cap before invoking ``tier``; return True to downshift.

        A downshift is only possible past the cheapest tier — if even the first
        tier is unaffordable there is nothing cheaper to fall back to, so the run
        aborts regardless of policy.
        """
        meter = self._meter
        if meter is None or not meter.would_exceed_cost(tier.estimated_cost):
            return False
        if self._policy is SpendCapPolicy.DOWNSHIFT and index > 0:
            decisions.append(f"{tier.name}: spend cap reached -> downshift (skip)")
            return True
        decisions.append(f"{tier.name}: spend cap exceeded -> abort")
        meter.spend_cost(tier.estimated_cost)  # raises BudgetBreachError
        return False  # unreachable: spend_cost raised

    @staticmethod
    def _best_outcome(
        value: Any,
        tier: str | None,
        confidence: float | None,
        attempted: list[str],
        decisions: list[str],
    ) -> CascadeOutcome:
        """Build the terminal outcome when no tier's output cleared its floor."""
        return CascadeOutcome(
            value=value,
            chosen=tier,
            succeeded=False,
            escalated=True,
            attempted=tuple(attempted),
            decisions=tuple(decisions),
            confidence=confidence,
        )
