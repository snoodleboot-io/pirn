"""``FailoverLoop`` — try failover candidates one at a time, stopping at the first success.

A ``LoopSubTapestry`` that builds only the candidates actually attempted: once
the accumulated result has succeeded, or every candidate has been tried, the
loop stops. The candidates and breakers ride the loop state
(:class:`FailoverLoopState`), so the loop holds no per-run instance state.

Algorithm:
    ``step(state)`` builds one iteration for the next candidate:

    1. With breakers, a :class:`CircuitClosedCheck` acquires the candidate's
       breaker and closes a ``Gate`` when it is open.
    2. :class:`CandidateCall` awaits the operation under
       ``KnotConfig(timeout=candidate.timeout)`` — the engine owns the bound
       and records an overrun as ``Err(KnotTimeoutError)``. Behind a closed
       gate it is skipped with reason ``"circuit_open"``.
    3. :class:`AttemptCandidate` (``RECEIVE_ERRORS``) folds the call's
       ``Ok``/``Err``/``Skipped`` into the trace and the breaker.

    ``fold`` adopts the folded trace. A failed call is an ``Err`` inside the
    iteration, not a failed loop, so the loop tolerates iteration failures and
    ``fold`` refuses only a run whose fold knot itself produced no value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.gate.gate import Gate
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.nodes.sub_tapestry_error import SubTapestryError
from pirn.tapestry import Tapestry

from pirn_agents.resilience.attempt_candidate import AttemptCandidate
from pirn_agents.resilience.candidate_call import CandidateCall
from pirn_agents.resilience.circuit_closed_check import CircuitClosedCheck
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_loop_state import FailoverLoopState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class FailoverLoop(LoopSubTapestry[FailoverLoopState]):
    """Attempt failover candidates in order, stopping at the first success."""

    #: A candidate's failure is an ``Err`` its fold knot receives, not a loop failure.
    _tolerate_iteration_failures: ClassVar[bool] = True

    #: Per-iteration knot id of the fold (no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def step(self, state: FailoverLoopState) -> tuple[Tapestry, FailoverLoopState] | None:
        """Build the next candidate's attempt, or None once succeeded or exhausted.

        Args:
            state: The chain's inputs and the trace from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` to stop.
        """
        candidate = state.next_candidate()
        if candidate is None:
            return None

        attempt = Tapestry()
        with attempt:
            call_input: Knot = Parameter(
                "candidate",
                FailoverCandidate,
                default=candidate,
                _config=KnotConfig(id="candidate"),
            )
            if state.breakers is not None:
                call_input = Gate(
                    input=call_input,
                    check=CircuitClosedCheck(
                        candidate=candidate,
                        breakers=state.breakers,
                        _config=KnotConfig(id="circuit"),
                    ),
                    _config=KnotConfig(id="circuit_gate"),
                )
            call = CandidateCall(
                candidate=call_input,
                _config=KnotConfig(id="call", timeout=candidate.timeout),
            )
            AttemptCandidate(
                prior=state.result,
                candidate=candidate,
                breakers=state.breakers,
                outcome=call,
                _config=KnotConfig(id=self._attempt_id, error_policy=ErrorPolicy.RECEIVE_ERRORS),
            )
        return attempt, state

    def fold(self, state: FailoverLoopState, result: RunResult) -> FailoverLoopState:
        """Adopt the candidate's folded trace.

        Args:
            state: State as ``step`` returned it.
            result: The attempt's run result.

        Returns:
            ``state`` carrying the trace ``AttemptCandidate`` returned.

        Raises:
            SubTapestryError: If the fold knot itself produced no value.
        """
        if self._attempt_id not in result.outputs:
            raise SubTapestryError(result)
        return FailoverLoopState(
            candidates=state.candidates,
            breakers=state.breakers,
            result=result.outputs[self._attempt_id],
        )

    def step_id(self, state: FailoverLoopState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
