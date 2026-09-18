"""``CascadeLoop`` — try cascade tiers one at a time, stopping at the first accept.

Replaces the static chain of one ``AttemptTier`` knot per tier that
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

from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.routing.attempt_tier import AttemptTier
from pirn_agents.specializations.routing.cascade_chain_state import CascadeChainState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class CascadeLoop(AgentLoopPipeline[CascadeChainState]):
    """Attempt cascade tiers in order, stopping at the first accepted (or downshifted) tier."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def step(self, state: CascadeChainState) -> tuple[Tapestry, CascadeChainState] | None:
        """Build the next tier's attempt, or None once locked or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.locked`` or every tier has been processed.
        """
        tier = state.next_tier()
        if tier is None:
            return None

        attempt = Tapestry()
        with attempt:
            AttemptTier(
                prior=state,
                tier=tier,
                index=len(state.decisions),
                request=state.request,
                confidence=state.confidence,
                meter=state.meter,
                spend_cap_policy=state.spend_cap_policy,
                _config=KnotConfig(id=self._attempt_id),
            )
        return attempt, state

    def fold(self, state: CascadeChainState, result: RunResult) -> CascadeChainState:
        """Adopt the tier's folded state.

        Args:
            state: State as ``step`` returned it (unused -- ``AttemptTier``
                already folded ``prior`` into its own resolved output).
            result: The attempt's run result.

        Returns:
            The state ``AttemptTier`` returned.
        """
        return result.outputs[self._attempt_id]

    def step_id(self, state: CascadeChainState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
