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

``tiers`` is a resolved value known in full by the time ``process()`` runs, so
its length is not data-dependent (unlike an agentic loop), but the chain is
still driven by a
:class:`~pirn_agents.specializations.routing._cascade_loop._CascadeLoop`
(``LoopSubTapestry``) rather than a static unroll (ADR agents-speaks-core
WS5b): once a tier is accepted, or the spend cap forces a downshift, the
state is ``locked`` and the loop stops, so a tier past that point is never
even scheduled — the same escalation-stops-here behaviour as before, except
every *attempted* tier now gets its own engine ``Result``, history record,
and lineage, where the original hid all of them behind one knot's hand-rolled
loop.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.interfaces.router import Router
from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.routing._cascade_chain_state import _CascadeChainState
from pirn_agents.specializations.routing._cascade_loop import _CascadeLoop
from pirn_agents.specializations.routing._cascade_result import _CascadeResult
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class ModelCascadeRouter(AgentPipeline, Router):
    """Route to cost-ordered model tiers, escalating on low confidence or failure."""

    def __init__(
        self,
        *,
        request: Knot | Any,
        tiers: Knot | Sequence[CascadeTier],
        confidence: Any,
        meter: Any = None,
        spend_cap_policy: Knot | SpendCapPolicy = SpendCapPolicy.DOWNSHIFT,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire the cascade's inputs.

        Args:
            request: The payload to route, or a :class:`Knot` producing it.
            tiers: The model tiers to try in order, cheapest first.
            confidence: Async scorer mapping a tier's output to ``[0, 1]``.
            meter: Optional budget meter.
            spend_cap_policy: What to do when escalating would breach the cap.
            _config: Knot configuration carrying this router's graph id.
            **kwargs: Forwarded to :class:`~pirn.nodes.sub_tapestry.SubTapestry`.
        """
        super().__init__(
            request=request,
            tiers=tiers,
            confidence=confidence,
            meter=meter,
            spend_cap_policy=spend_cap_policy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        request: Any,
        tiers: Sequence[CascadeTier],
        confidence: Callable[[Any], Awaitable[float]],
        # `meter` is typed `Any`: RunBudgetMeter is a plain class, not a
        # PirnOpaqueValue, and pydantic has no schema for it -- see
        # `_AttemptTier`'s docstring for why a concrete annotation breaks
        # `Knot.__init__`'s eager TypeAdapter construction.
        meter: Any = None,
        spend_cap_policy: SpendCapPolicy = SpendCapPolicy.DOWNSHIFT,
        **_: Any,
    ) -> Knot:
        """Build the tier chain and return its outcome-extracting sink knot.

        Args:
            request: The payload passed unchanged to each tier's ``invoke``.
            tiers: The model tiers to try in order; must be non-empty and each a
                :class:`CascadeTier`.
            confidence: Async scorer mapping a tier's output to a confidence in
                ``[0, 1]`` — the pluggable escalation trigger.
            meter: Optional budget meter; when present each tier's estimated cost
                accrues into it and the spend cap is enforced.
            spend_cap_policy: What to do when escalating would breach the cost
                cap — abort the run or downshift (stop escalating).

        Returns:
            The sink knot whose output is a :class:`CascadeOutcome` carrying
            the value, the chosen tier, and the full decision log.

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

        initial = Parameter(
            "initial",
            _CascadeChainState,
            default=_CascadeChainState(),
        )
        loop = _CascadeLoop(
            request=request,
            tiers=tier_tuple,
            confidence=confidence,
            meter=meter,
            spend_cap_policy=spend_cap_policy,
            state=initial,
            _config=KnotConfig(id="cascade_loop"),
        )
        return _CascadeResult(state=loop, _config=KnotConfig(id="result"))
