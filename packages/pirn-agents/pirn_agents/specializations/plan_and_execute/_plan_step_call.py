"""``_PlanStepCall`` — one LLM call executing a single plan step.

Internal per-iteration knot for :class:`~pirn_agents.specializations.plan_and_execute.plan_executor.PlanExecutor`'s
sequential loop. Each call receives the prior steps' results as context, so
the LLM can build on previous outputs — exactly the sequential dependency
that makes this a ``LoopSubTapestry`` iteration rather than a fan-out.

Algorithm:
    1. Render the prior-steps context (empty for the first step).
    2. Build the system + user messages for this step.
    3. Call ``llm.chat`` and extract the plain-text result.

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _PlanStepCall(Knot):
    """Execute one plan step via a single LLM call, given prior results as context."""

    _step_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.plan_and_execute.plan_executor.step_system",
        default=(
            "You are a task executor. Complete the given step accurately and concisely. "
            "Use the previous step results as context where relevant."
        ),
    )

    def __init__(
        self,
        *,
        step_index: Knot | int,
        step_text: Knot | str,
        prior_results: Knot | tuple[str, ...],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            step_index=step_index,
            step_text=step_text,
            prior_results=prior_results,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        step_index: int,
        step_text: str,
        prior_results: tuple[str, ...],
        llm: LLMProvider,
        **_: Any,
    ) -> str:
        """Execute one plan step and return the LLM's plain-text result.

        Args:
            step_index: 0-based index of this step within the plan.
            step_text: This step's free-form description.
            prior_results: Every earlier step's result, in order.
            llm: The LLM provider used to execute the step.

        Returns:
            The extracted plain-text result of this step's LLM call.
        """
        prior_context = "\n".join(f"Step {i + 1} result: {r}" for i, r in enumerate(prior_results))
        user_content = (
            f"Step {step_index + 1}: {step_text}"
            if not prior_context
            else f"{prior_context}\n\nStep {step_index + 1}: {step_text}"
        )
        messages = [
            {"role": "system", "content": type(self)._step_system.resolve()},
            {"role": "user", "content": user_content},
        ]
        raw = await llm.chat(messages=messages)
        return LlmResponseText().extract(raw)
