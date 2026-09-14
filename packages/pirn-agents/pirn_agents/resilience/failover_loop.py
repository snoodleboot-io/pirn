"""``FailoverLoop`` — try failover candidates one at a time, stopping at the first success.

Replaces the static chain of one ``AttemptCandidate`` knot per candidate that
``FailoverChain`` unrolled up front — every candidate got a knot even after
the chain had already succeeded, each already-succeeded candidate merely
passing the result through unchanged — with a ``LoopSubTapestry`` that builds
only the candidates actually attempted: once ``state.succeeded`` is set, the
loop stops (ADR agents-speaks-core WS5b).

``FailoverChain`` keeps its public shape (constructor, return type); only
this internal drive mechanism changes.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.resilience.attempt_candidate import AttemptCandidate
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_result import FailoverResult
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class FailoverLoop(AgentLoopPipeline[FailoverResult]):
    """Attempt failover candidates in order, stopping at the first success."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def __init__(
        self,
        *,
        candidates: tuple[FailoverCandidate, ...],
        breakers: Any,
        **kwargs: Any,
    ) -> None:
        self._candidates = candidates
        self._breakers = breakers
        super().__init__(**kwargs)

    def step(self, state: FailoverResult) -> tuple[Tapestry, FailoverResult] | None:
        """Build the next candidate's attempt, or None once succeeded or exhausted.

        Args:
            state: Accumulated result from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.succeeded`` or every candidate has been tried.
        """
        index = len(state.attempts)
        if state.succeeded or index >= len(self._candidates):
            return None

        attempt = Tapestry()
        with attempt:
            AttemptCandidate(
                prior=state,
                candidate=self._candidates[index],
                breakers=self._breakers,
                _config=KnotConfig(id=self._attempt_id),
            )
        return attempt, state

    def fold(self, state: FailoverResult, result: RunResult) -> FailoverResult:
        """Adopt the candidate's folded result.

        Args:
            state: State as ``step`` returned it (unused -- ``AttemptCandidate``
                already folded ``prior`` into its own resolved output).
            result: The attempt's run result.

        Returns:
            The result ``AttemptCandidate`` returned.
        """
        return result.outputs[self._attempt_id]

    def step_id(self, state: FailoverResult, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
