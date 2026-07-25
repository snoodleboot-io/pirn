"""``EvaluatorOptimizerPipeline`` — generator + LLM-judge + scored accept gate.

A :class:`SubTapestry` that loops, up to ``max_iterations`` times:

1. :class:`CandidateGenerator` drafts a candidate (refining on the last judge
   feedback).
2. :class:`LlmJudge` scores the candidate.
3. :class:`AcceptGate` — the scored generalisation of
   :class:`~pirn_agents.control.reflection_check.ReflectionCheck` — accepts once
   the score meets ``threshold``.

To *reuse rather than duplicate* the existing binary gate, the pipeline also
accepts an optional injected :class:`ReflectionCheck`; when supplied it is
consulted as an early-stop signal — if it decides no further iteration is
worthwhile, the loop stops with the best candidate so far. The loop is bounded by
``max_iterations`` and returns a typed :class:`EvaluatorOptimizerResult`.

References:
    - Madaan et al. (2023) "Self-Refine" https://arxiv.org/abs/2303.17651
    - Anthropic (2024) "Building effective agents" — evaluator-optimizer
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.evaluator_optimizer.accept_gate import AcceptGate
from pirn_agents.specializations.evaluator_optimizer.candidate_generator import CandidateGenerator
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_result import (
    EvaluatorOptimizerResult,
)
from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.evaluator_optimizer.llm_judge import LlmJudge
from pirn_agents.types.agent_response import AgentResponse


class EvaluatorOptimizerPipeline(SubTapestry):
    """Generate → judge → accept loop with a scored gate."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        threshold: Knot | float = 8.0,
        max_iterations: Knot | int = 3,
        reflection_gate: ReflectionCheck | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._reflection_gate = reflection_gate
        super().__init__(
            task=task,
            llm=llm,
            threshold=threshold,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        threshold: float = 8.0,
        max_iterations: int = 3,
        **_: Any,
    ) -> Any:
        """Run the accept loop and surface an :class:`EvaluatorOptimizerResult`.

        Args:
            task: The task to answer.
            llm: Provider shared by the generator and judge.
            threshold: Minimum judge score (0-10) to accept.
            max_iterations: Hard cap on generate/judge rounds.

        Returns:
            A terminal :class:`Source` whose output is the
            :class:`EvaluatorOptimizerResult`.

        Raises:
            TypeError: If ``llm``/``task``/``threshold`` have the wrong type.
            ValueError: If ``max_iterations`` is not a positive int.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"EvaluatorOptimizerPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(
                f"EvaluatorOptimizerPipeline: task must be a string, got {type(task).__name__}"
            )
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise TypeError(
                "EvaluatorOptimizerPipeline: threshold must be numeric, got "
                f"{type(threshold).__name__}"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "EvaluatorOptimizerPipeline: max_iterations must be a positive int, got "
                f"{max_iterations!r}"
            )

        with Tapestry():
            generator = CandidateGenerator(task=task, llm=llm, _config=KnotConfig(id="eo_gen"))
            judge = LlmJudge(task=task, candidate="", llm=llm, _config=KnotConfig(id="eo_judge"))
            gate = AcceptGate(
                verdict=JudgeVerdict(score=0.0),
                threshold=threshold,
                _config=KnotConfig(id="eo_gate"),
            )

        gate_check = self._reflection_gate
        feedback = ""
        best_answer = ""
        best_score = 0.0
        accepted = False
        iterations = 0

        for index in range(max_iterations):
            iterations = index + 1
            candidate = await generator.process(task=task, llm=llm, feedback=feedback)
            verdict = await judge.process(task=task, candidate=candidate, llm=llm)
            if verdict.score >= best_score or index == 0:
                best_answer = candidate
                best_score = verdict.score
            if await gate.process(verdict=verdict, threshold=threshold):
                accepted = True
                break
            feedback = verdict.feedback
            if gate_check is not None:
                iterate_again = await gate_check.process(
                    response=AgentResponse(content=candidate), llm=llm
                )
                if not iterate_again:
                    break

        result = EvaluatorOptimizerResult(
            answer=best_answer,
            score=best_score,
            accepted=accepted,
            iterations=iterations,
        )
        _result = result

        class _EvaluatorOptimizerResultSource(Source):
            async def process(self, **_: Any) -> EvaluatorOptimizerResult:
                return _result

        return _EvaluatorOptimizerResultSource(_config=KnotConfig(id="eo_result"))
