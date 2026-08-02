"""``_EvaluatorOptimizerLoop`` — the generate/judge/accept loop as a core node.

Replaces the hand-rolled ``for index in range(max_iterations)`` that awaited
``generator/judge/gate.process()`` directly, so every iteration is an engine
knot with its own ``Result``, history record and lineage.

Both termination decisions live inside the iteration tapestry, per
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
— that base explains why. Concretely: ``AcceptGate`` is a knot rather than an
awaited call in a Python ``if``, and the optional ``ReflectionCheck`` sits behind
a ``Gate`` that opens only on "not accepted", so an accepted run does not pay for
it.

Internal API. See PIR-713.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.base.gated_agent_response import GatedAgentResponse
from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_state import (
    _EvaluatorOptimizerState,
)
from pirn_agents.specializations.evaluator_optimizer.accept_gate import AcceptGate
from pirn_agents.specializations.evaluator_optimizer.candidate_generator import (
    CandidateGenerator,
)
from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.evaluator_optimizer.llm_judge import LlmJudge

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult

_GEN_ID = "eo_gen"
_JUDGE_ID = "eo_judge"
_GATE_ID = "eo_gate"
_CONTINUE_ID = "eo_continue"
_REFLECT_ID = "eo_reflect"


def _reject(accepted: bool) -> bool:
    """Open the continue-gate only when the candidate was *not* accepted."""
    return not accepted


class _EvaluatorOptimizerLoop(AgentLoopPipeline[_EvaluatorOptimizerState]):
    """Iterate generate → judge → accept until accepted, stopped, or capped."""

    def __init__(
        self,
        *,
        task: str,
        llm: LLMProvider,
        threshold: float,
        max_iterations: int,
        reflection_gate: ReflectionCheck | None,
        **kwargs: Any,
    ) -> None:
        self._task = task
        self._llm = llm
        self._threshold = threshold
        self._max_iterations = max_iterations
        self._reflection_gate = reflection_gate
        super().__init__(**kwargs)

    def step(
        self, state: _EvaluatorOptimizerState
    ) -> tuple[Tapestry, _EvaluatorOptimizerState] | None:
        """Build the next iteration, or return None to terminate.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The iteration's tapestry paired with the state ``fold`` will
            receive, or ``None`` once accepted, stopped, or capped.
        """
        if state.accepted or state.stop or state.iterations >= self._max_iterations:
            return None

        iteration = Tapestry()
        with iteration:
            candidate = CandidateGenerator(
                task=self._task,
                llm=self._llm,
                feedback=state.feedback,
                _config=KnotConfig(id=_GEN_ID),
            )
            verdict = LlmJudge(
                task=self._task,
                candidate=candidate,
                llm=self._llm,
                _config=KnotConfig(id=_JUDGE_ID),
            )
            accepted = AcceptGate(
                verdict=verdict,
                threshold=self._threshold,
                _config=KnotConfig(id=_GATE_ID),
            )
            if self._reflection_gate is not None:
                keep_going = Gate(
                    input=accepted,
                    predicate=_reject,
                    _config=KnotConfig(id=_CONTINUE_ID),
                )
                response = GatedAgentResponse(
                    content=candidate,
                    gate=keep_going,
                    _config=KnotConfig(id="eo_candidate_response"),
                )
                ReflectionCheck(
                    response=response,
                    llm=self._llm,
                    _config=KnotConfig(id=_REFLECT_ID),
                )
        return iteration, state

    def fold(self, state: _EvaluatorOptimizerState, result: RunResult) -> _EvaluatorOptimizerState:
        """Integrate one iteration's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The iteration's run result.

        Returns:
            A new state carrying the iteration's outcome.
        """
        candidate = result.outputs.get(_GEN_ID, "")
        verdict = result.outputs.get(_JUDGE_ID)
        score = verdict.score if isinstance(verdict, JudgeVerdict) else 0.0
        accepted = bool(result.outputs.get(_GATE_ID, False))
        iterations = state.iterations + 1

        # First iteration always seeds the best; later ones only improve it.
        improved = iterations == 1 or score >= state.best_score
        best_answer = candidate if improved else state.best_answer
        best_score = score if improved else state.best_score

        # Absent when the continue-gate closed (i.e. the candidate was
        # accepted) or when no reflection gate was supplied at all. Only an
        # explicit "do not continue" stops the loop early.
        keep_going = result.outputs.get(_REFLECT_ID)
        stop = keep_going is False

        return _EvaluatorOptimizerState(
            feedback=verdict.feedback if isinstance(verdict, JudgeVerdict) else "",
            best_answer=best_answer,
            best_score=best_score,
            accepted=accepted,
            iterations=iterations,
            stop=stop,
        )

    def step_id(self, state: _EvaluatorOptimizerState, idx: int) -> str:
        """Name each iteration for run history."""
        return f"eo_iteration_{idx}"
