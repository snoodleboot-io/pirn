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

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_loop import (
    _EvaluatorOptimizerLoop,
)
from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_result_builder import (
    _EvaluatorOptimizerResultBuilder,
)
from pirn_agents.specializations.evaluator_optimizer._initial_loop_state import (
    _InitialLoopState,
)


class EvaluatorOptimizerPipeline(AgentPipeline):
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

        initial = _InitialLoopState(_config=KnotConfig(id="eo_initial_state"))
        loop = _EvaluatorOptimizerLoop(
            task=task,
            llm=llm,
            threshold=float(threshold),
            max_iterations=max_iterations,
            reflection_gate=self._reflection_gate,
            state=initial,
            _config=KnotConfig(id="eo_loop"),
        )
        return _EvaluatorOptimizerResultBuilder(
            state=loop,
            _config=KnotConfig(id="eo_result"),
        )
