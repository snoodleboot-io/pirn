"""``EvaluatorOptimizerLoop`` — the generate/judge/accept loop as a core node.

Replaces the hand-rolled ``for index in range(max_iterations)`` that awaited
``generator/judge/gate.process()`` directly, so every iteration is an engine
knot with its own ``Result``, history record and lineage.

Both termination decisions live inside the iteration tapestry, per
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
— that base explains why. Concretely: ``AcceptCheck`` is a knot rather than an
awaited call in a Python ``if``, and the optional ``ReflectionCheck`` sits behind
a core ``Gate(input=candidate, check=CandidateRejectedCheck(accepted))`` that
opens only on "not accepted", so an accepted run does not pay for it.

Internal API. See PIR-713.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.evaluator_optimizer._candidate_rejected_check import (
    CandidateRejectedCheck,
)
from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_state import (
    EvaluatorOptimizerState,
)
from pirn_agents.specializations.evaluator_optimizer.accept_check import AcceptCheck
from pirn_agents.specializations.evaluator_optimizer.candidate_generator import (
    CandidateGenerator,
)
from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.evaluator_optimizer.llm_judge import LlmJudge
from pirn_agents.specializations.rag.rag_response_builder import RAGResponseBuilder

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class EvaluatorOptimizerLoop(AgentLoopPipeline[EvaluatorOptimizerState]):
    """Iterate generate → judge → accept until accepted, stopped, or capped."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _gen_id: ClassVar[str] = "eo_gen"
    _judge_id: ClassVar[str] = "eo_judge"
    _gate_id: ClassVar[str] = "eo_gate"
    _rejected_id: ClassVar[str] = "eo_rejected"
    _continue_id: ClassVar[str] = "eo_continue"
    _reflect_id: ClassVar[str] = "eo_reflect"

    def __init__(
        self,
        *,
        task: str,
        llm: LLMProvider,
        threshold: float,
        max_iterations: int,
        reflection_gate: bool,
        **kwargs: Any,
    ) -> None:
        self._task = task
        self._llm = llm
        self._threshold = threshold
        self._max_iterations = max_iterations
        self._reflection_gate = reflection_gate
        super().__init__(**kwargs)

    def step(
        self, state: EvaluatorOptimizerState
    ) -> tuple[Tapestry, EvaluatorOptimizerState] | None:
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
                _config=KnotConfig(id=self._gen_id),
            )
            verdict = LlmJudge(
                task=self._task,
                candidate=candidate,
                llm=self._llm,
                _config=KnotConfig(id=self._judge_id),
            )
            accepted = AcceptCheck(
                verdict=verdict,
                threshold=self._threshold,
                _config=KnotConfig(id=self._gate_id),
            )
            if self._reflection_gate:
                rejected = CandidateRejectedCheck(
                    accepted=accepted, _config=KnotConfig(id=self._rejected_id)
                )
                gated_candidate = Gate(
                    input=candidate,
                    check=rejected,
                    _config=KnotConfig(id=self._continue_id),
                )
                response = RAGResponseBuilder(
                    answer=gated_candidate,
                    _config=KnotConfig(id="eo_candidate_response"),
                )
                ReflectionCheck(
                    response=response,
                    llm=self._llm,
                    _config=KnotConfig(id=self._reflect_id),
                )
        return iteration, state

    def fold(self, state: EvaluatorOptimizerState, result: RunResult) -> EvaluatorOptimizerState:
        """Integrate one iteration's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The iteration's run result.

        Returns:
            A new state carrying the iteration's outcome.
        """
        candidate = result.outputs.get(self._gen_id, "")
        verdict = result.outputs.get(self._judge_id)
        score = verdict.score if isinstance(verdict, JudgeVerdict) else 0.0
        accepted = bool(result.outputs.get(self._gate_id, False))
        iterations = state.iterations + 1

        # First iteration always seeds the best; later ones only improve it.
        improved = iterations == 1 or score >= state.best_score
        best_answer = candidate if improved else state.best_answer
        best_score = score if improved else state.best_score

        # Absent when the continue-gate closed (i.e. the candidate was
        # accepted) or when no reflection gate was supplied at all. Only an
        # explicit "do not continue" stops the loop early.
        keep_going = result.outputs.get(self._reflect_id)
        stop = keep_going is False

        return EvaluatorOptimizerState(
            feedback=verdict.feedback if isinstance(verdict, JudgeVerdict) else "",
            best_answer=best_answer,
            best_score=best_score,
            accepted=accepted,
            iterations=iterations,
            stop=stop,
        )

    def step_id(self, state: EvaluatorOptimizerState, idx: int) -> str:
        """Name each iteration for run history."""
        return f"eo_iteration_{idx}"
