"""``_AttemptTier`` — fold one cascade tier's decision into state."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing._cascade_chain_state import _CascadeChainState
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class _AttemptTier(Knot):
    """Fold one tier's decision into the cascade's accumulated state.

    ``confidence`` and ``meter`` are typed ``Any``: ``confidence`` is a bare
    callable (not a :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`) and
    :class:`RunBudgetMeter` is a plain class, so pydantic has no schema for
    either — ``Knot.__init__`` builds a ``TypeAdapter`` for every declared
    input eagerly, and a concrete annotation would raise
    ``PydanticSchemaGenerationError`` at construction time. This mirrors why
    the pre-remediation version of this file routed both around
    ``super().__init__()`` entirely.
    """

    def __init__(
        self,
        *,
        prior: Knot | _CascadeChainState,
        tier: Knot | CascadeTier,
        index: Knot | int,
        request: Knot | Any,
        confidence: Any,
        meter: Any,
        spend_cap_policy: Knot | SpendCapPolicy,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior,
            tier=tier,
            index=index,
            request=request,
            confidence=confidence,
            meter=meter,
            spend_cap_policy=spend_cap_policy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prior: _CascadeChainState,
        tier: CascadeTier,
        index: int,
        request: Any,
        confidence: Callable[[Any], Awaitable[float]],
        meter: Any,
        spend_cap_policy: SpendCapPolicy,
        **_: Any,
    ) -> _CascadeChainState:
        """Try ``tier`` unless the chain is already locked.

        Args:
            prior: The chain's accumulated state before this tier.
            tier: This tier's name, invoke callable, floor, and cost.
            index: This tier's 0-based position (0 = cheapest).
            request: The payload passed unchanged to the tier's ``invoke``.
            confidence: Async scorer mapping the tier's output to ``[0, 1]``.
            meter: Optional budget meter accruing each tier's estimated cost.
            spend_cap_policy: What to do when a tier would breach the cap.

        Returns:
            ``prior`` unchanged if already locked (accepted or downshifted);
            otherwise the state folding in this tier's decision.

        Raises:
            pirn_agents.performance.budget_breach_error.BudgetBreachError: When
                the spend cap is exceeded under an ``ABORT`` policy.
        """
        if prior.locked:
            return prior
        decisions = list(prior.decisions)
        attempted = list(prior.attempted)

        if meter is not None and meter.would_exceed_cost(tier.estimated_cost):
            if spend_cap_policy is SpendCapPolicy.DOWNSHIFT and index > 0:
                decisions.append(f"{tier.name}: spend cap reached -> downshift (skip)")
                return _CascadeChainState(
                    attempted=tuple(attempted),
                    decisions=tuple(decisions),
                    best_value=prior.best_value,
                    best_tier=prior.best_tier,
                    best_confidence=prior.best_confidence,
                    locked=True,
                )
            decisions.append(f"{tier.name}: spend cap exceeded -> abort")
            meter.spend_cost(tier.estimated_cost)  # raises BudgetBreachError

        attempted.append(tier.name)
        try:
            value = await tier.invoke(request)
        except Exception as exc:
            decisions.append(f"{tier.name}: failed ({exc}) -> escalate")
            return _CascadeChainState(
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                best_value=prior.best_value,
                best_tier=prior.best_tier,
                best_confidence=prior.best_confidence,
            )

        if meter is not None:
            meter.spend_cost(tier.estimated_cost)

        score = float(await confidence(value))
        if score >= tier.min_confidence:
            decisions.append(f"{tier.name}: accepted (confidence={score})")
            outcome = CascadeOutcome(
                value=value,
                chosen=tier.name,
                succeeded=True,
                escalated=index > 0,
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                confidence=score,
            )
            return _CascadeChainState(
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                accepted_outcome=outcome,
                locked=True,
            )
        decisions.append(f"{tier.name}: low confidence={score} -> escalate")
        return _CascadeChainState(
            attempted=tuple(attempted),
            decisions=tuple(decisions),
            best_value=value,
            best_tier=tier.name,
            best_confidence=score,
        )
