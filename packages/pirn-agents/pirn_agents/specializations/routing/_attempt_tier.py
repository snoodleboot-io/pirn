"""``_AttemptTier`` — fold one cascade tier's decision into state.

A cascade tier is a model call, so it runs as the same LLM-call knot the
other patterns use:
:class:`~pirn_agents.specializations.rag.llm_chat_call.LLMChatCall` over the
tier's provider, dispatched by the engine with its own ``Result``, lineage row
and ``"llm"`` call event — nothing awaits a provider inside ``process()``
(PIR-872). :class:`~pirn_agents.specializations.routing._tier_attempt_fold._TierAttemptFold`
— wired with ``error_policy=RECEIVE_ERRORS`` over it — folds the raw
``Ok``/``Err`` outcome into the cascade's state, exactly like
``ReActStepExecutor``'s tool-call assembler does for a tool call. The
locked / spend-cap decisions that must run *before* any provider call is
made stay synchronous here, since they decide whether to build that call at
all.
"""

from __future__ import annotations

from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.routing._cascade_chain_state import _CascadeChainState
from pirn_agents.specializations.routing._tier_attempt_fold import _TierAttemptFold
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class _AttemptTier(AgentPipeline):
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

    # A failed invocation is delivered to _TierAttemptFold, not to this knot.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        prior: Knot | _CascadeChainState,
        tier: Knot | CascadeTier,
        index: Knot | int,
        request: Knot | str,
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
        request: str,
        confidence: Any,
        meter: Any,
        spend_cap_policy: SpendCapPolicy,
        **_: Any,
    ) -> Knot:
        """Decide whether to try ``tier``, and return the knot resolving to the folded state.

        Args:
            prior: The chain's accumulated state before this tier.
            tier: This tier's name, provider, floor, and cost.
            index: This tier's 0-based position (0 = cheapest).
            request: The prompt sent unchanged to the tier's provider.
            confidence: Async scorer mapping the tier's output to ``[0, 1]``.
            meter: Optional budget meter accruing each tier's estimated cost.
            spend_cap_policy: What to do when a tier would breach the cap.

        Returns:
            A ``Parameter`` defaulting to ``prior`` unchanged when the chain
            is already locked, or to the downshift state when the spend cap
            triggers a skip; otherwise the sink of the inner pipeline — a
            ``_TierAttemptFold`` over the wired ``LLMChatCall`` — whose
            output is the state folding in this tier's decision.

        Raises:
            pirn_agents.performance.budget_breach_error.BudgetBreachError: When
                the spend cap is exceeded under an ``ABORT`` policy.
        """
        if prior.locked:
            return Parameter(
                "locked", _CascadeChainState, default=prior, _config=KnotConfig(id="locked")
            )

        if meter is not None and meter.would_exceed_cost(tier.estimated_cost):
            decisions = list(prior.decisions)
            if spend_cap_policy is SpendCapPolicy.DOWNSHIFT and index > 0:
                decisions.append(f"{tier.name}: spend cap reached -> downshift (skip)")
                return Parameter(
                    "downshift",
                    _CascadeChainState,
                    default=_CascadeChainState(
                        attempted=prior.attempted,
                        decisions=tuple(decisions),
                        best_value=prior.best_value,
                        best_tier=prior.best_tier,
                        best_confidence=prior.best_confidence,
                        locked=True,
                    ),
                    _config=KnotConfig(id="downshift"),
                )
            decisions.append(f"{tier.name}: spend cap exceeded -> abort")
            meter.spend_cost(tier.estimated_cost)  # raises BudgetBreachError

        outcome = LLMChatCall(prompt=request, llm=tier.llm, _config=KnotConfig(id="invoke"))
        return _TierAttemptFold(
            prior=prior,
            tier=tier,
            index=index,
            confidence=confidence,
            meter=meter,
            outcome=outcome,
            _config=KnotConfig(id="fold", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )
