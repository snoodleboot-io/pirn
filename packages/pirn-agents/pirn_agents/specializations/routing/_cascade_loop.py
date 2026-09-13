"""``_CascadeLoop`` — try cascade tiers one at a time, stopping at the first accept.

Replaces the static chain of one ``_AttemptTier`` knot per tier that
``ModelCascadeRouter`` unrolled up front — every tier got a knot even after
the chain had already locked, each locked tier merely passing the state
through unchanged — with a ``LoopSubTapestry`` that builds only the tiers
actually attempted: once ``state.locked`` is set, the loop stops, so a tier
past the accepted one is never even scheduled (ADR agents-speaks-core WS5b).

``ModelCascadeRouter`` keeps its public shape (constructor, return type); only
this internal drive mechanism changes.

Internal API. See PIR-856.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.routing._attempt_tier import _AttemptTier
from pirn_agents.specializations.routing._cascade_chain_state import _CascadeChainState
from pirn_agents.specializations.routing.cascade_tier import CascadeTier

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class _CascadeLoop(AgentLoopPipeline[_CascadeChainState]):
    """Attempt cascade tiers in order, stopping at the first accepted (or downshifted) tier."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def __init__(
        self,
        *,
        request: Any,
        tiers: tuple[CascadeTier, ...],
        confidence: Callable[[Any], Awaitable[float]],
        meter: Any,
        spend_cap_policy: SpendCapPolicy,
        **kwargs: Any,
    ) -> None:
        self._request = request
        self._tiers = tiers
        self._confidence = confidence
        self._meter = meter
        self._spend_cap_policy = spend_cap_policy
        super().__init__(**kwargs)

    def step(self, state: _CascadeChainState) -> tuple[Tapestry, _CascadeChainState] | None:
        """Build the next tier's attempt, or None once locked or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.locked`` or every tier has been processed.
        """
        index = len(state.decisions)
        if state.locked or index >= len(self._tiers):
            return None

        attempt = Tapestry()
        with attempt:
            _AttemptTier(
                prior=state,
                tier=self._tiers[index],
                index=index,
                request=self._request,
                confidence=self._confidence,
                meter=self._meter,
                spend_cap_policy=self._spend_cap_policy,
                _config=KnotConfig(id=self._attempt_id),
            )
        return attempt, state

    def fold(self, state: _CascadeChainState, result: RunResult) -> _CascadeChainState:
        """Adopt the tier's folded state.

        Args:
            state: State as ``step`` returned it (unused -- ``_AttemptTier``
                already folded ``prior`` into its own resolved output).
            result: The attempt's run result.

        Returns:
            The state ``_AttemptTier`` returned.
        """
        return result.outputs[self._attempt_id]

    def step_id(self, state: _CascadeChainState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
