"""``FallbackLoop`` — try fallback candidates one at a time, stopping at the first success.

Replaces the static chain of one ``CandidateAttempt`` knot per candidate that
``FallbackChain`` unrolled up front — every candidate got a knot even after
the chain had already locked, each locked candidate merely passing the state
through unchanged — with a ``LoopSubTapestry`` that builds only the
candidates actually attempted: once ``state.locked`` is set, the loop stops
(ADR agents-speaks-core WS5b).

``FallbackChain`` keeps its public shape (constructor, return type); only
this internal drive mechanism changes.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.routing.candidate_attempt import CandidateAttempt
from pirn_agents.specializations.routing.fallback_chain_state import FallbackChainState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class FallbackLoop(AgentLoopPipeline[FallbackChainState]):
    """Attempt fallback candidates in order, stopping at the first success."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def step(self, state: FallbackChainState) -> tuple[Tapestry, FallbackChainState] | None:
        """Build the next candidate's attempt, or None once locked or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.locked`` or every candidate has been processed.
        """
        candidate = state.next_candidate()
        if candidate is None:
            return None

        attempt = Tapestry()
        with attempt:
            CandidateAttempt(
                prior=state,
                candidate=candidate,
                arguments=state.arguments,
                confidences=state.confidences,
                _config=KnotConfig(id=self._attempt_id),
            )
        return attempt, state

    def fold(self, state: FallbackChainState, result: RunResult) -> FallbackChainState:
        """Adopt the candidate's folded state.

        Args:
            state: State as ``step`` returned it (unused -- ``CandidateAttempt``
                already folded ``prior`` into its own resolved output).
            result: The attempt's run result.

        Returns:
            The state ``CandidateAttempt`` returned.
        """
        return result.outputs[self._attempt_id]

    def step_id(self, state: FallbackChainState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
