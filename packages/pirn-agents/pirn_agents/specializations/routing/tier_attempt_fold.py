"""``TierAttemptFold`` — fold a tier's model-call ``Result`` into cascade state.

Internal knot for
:class:`~pirn_agents.specializations.routing.attempt_tier.AttemptTier`
(PIR-867). Wired with ``error_policy=RECEIVE_ERRORS`` over the tier's
:class:`~pirn_agents.specializations.rag.llm_chat_call.LLMChatCall` knot
(PIR-872), so ``outcome`` here is the call's raw ``Ok``/``Err`` — never
short-circuited to a knot-level failure — exactly like
:class:`~pirn_agents.specializations.react.react_step_executor._observation_assembler`
does for a tool call. A failed invocation folds into an "escalate" decision
the same way ``AttemptTier.process()`` used to fold a caught exception,
without the exception ever leaving the engine's own outcome handling.

Internal API.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped

from pirn_agents.specializations.routing.cascade_chain_state import CascadeChainState
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class TierAttemptFold(Knot):
    """Fold one tier invocation's outcome (success or failure) into cascade state."""

    def __init__(
        self,
        *,
        prior: Knot | CascadeChainState,
        tier: Knot | CascadeTier,
        index: Knot | int,
        confidence: Any,
        meter: Any,
        outcome: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior,
            tier=tier,
            index=index,
            confidence=confidence,
            meter=meter,
            outcome=outcome,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prior: CascadeChainState,
        tier: CascadeTier,
        index: int,
        confidence: Callable[[Any], Awaitable[float]],
        meter: Any,
        outcome: Ok[str] | Err | Skipped,
        **_: Any,
    ) -> CascadeChainState:
        """Fold this tier's invocation outcome into ``prior``.

        Args:
            prior: The chain's accumulated state before this tier.
            tier: This tier's name, provider, floor, and cost.
            index: This tier's 0-based position (0 = cheapest).
            confidence: Async scorer mapping the tier's output to ``[0, 1]``.
            meter: Optional budget meter accruing this tier's estimated cost
                on a successful invocation.
            outcome: The raw ``Result`` (``Ok`` on success, ``Err`` on a
                failed call) of the wired ``LLMChatCall``.

        Returns:
            ``prior`` folded with this tier's decision: escalate on a failed
            invocation, accept (locked) when the score clears
            ``tier.min_confidence``, otherwise escalate with this tier's
            output recorded as the new best candidate.
        """
        decisions = list(prior.decisions)
        attempted = [*prior.attempted, tier.name]

        if not isinstance(outcome, Ok):
            message = outcome.record.message if isinstance(outcome, Err) else "skipped"
            decisions.append(f"{tier.name}: failed ({message}) -> escalate")
            return CascadeChainState(
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                best_value=prior.best_value,
                best_tier=prior.best_tier,
                best_confidence=prior.best_confidence,
            )

        value = outcome.value
        if meter is not None:
            meter.spend_cost(tier.estimated_cost)

        score = float(await confidence(value))
        if score >= tier.min_confidence:
            decisions.append(f"{tier.name}: accepted (confidence={score})")
            cascade_outcome = CascadeOutcome(
                value=value,
                chosen=tier.name,
                succeeded=True,
                escalated=index > 0,
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                confidence=score,
            )
            return CascadeChainState(
                attempted=tuple(attempted),
                decisions=tuple(decisions),
                accepted_outcome=cascade_outcome,
                locked=True,
            )
        decisions.append(f"{tier.name}: low confidence={score} -> escalate")
        return CascadeChainState(
            attempted=tuple(attempted),
            decisions=tuple(decisions),
            best_value=value,
            best_tier=tier.name,
            best_confidence=score,
        )
