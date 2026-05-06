"""``PlanExecutor`` — executes each step of a Plan sequentially via LLM calls.

Algorithm:
    1. Receive the resolved ``plan`` (Plan) and ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Iterate over ``plan.steps`` in order.
    4. For each step, build a messages list that includes prior step results as context.
    5. Call ``llm.chat`` with the messages and extract the text result.
    6. Accumulate all step results and concatenate into a single AgentResponse.


References:
    - Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
    - Wang et al. (2023) "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.plan import Plan


class PlanExecutor(Knot):
    """Take a :class:`Plan` and execute each step via sequential sub-LLM calls.

    Each step is executed in order. The context for step N includes the
    results of all prior steps so the LLM can build on previous outputs.
    All step outputs are concatenated into the final :class:`AgentResponse`.
    """

    _step_system: str = (
        "You are a task executor. Complete the given step accurately and concisely. "
        "Use the previous step results as context where relevant."
    )

    def __init__(
        self,
        *,
        plan: Knot,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(plan=plan, llm=llm, _config=_config, **kwargs)

    async def process(self, plan: Plan, llm: LLMProvider, **_: Any) -> AgentResponse:
        """Execute each plan step sequentially and return an AgentResponse with all outputs.

        Args:
            plan: The Plan whose steps will be executed in order.

        Returns:
            An AgentResponse whose content contains each step result separated by newlines.

        Raises:
            TypeError: If plan is not a Plan instance.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"PlanExecutor: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(plan, Plan):
            raise TypeError(f"PlanExecutor: plan must be a Plan, got {type(plan).__name__}")
        step_results: list[str] = []
        for index, step in enumerate(plan.steps):
            prior_context = "\n".join(
                f"Step {i + 1} result: {r}" for i, r in enumerate(step_results)
            )
            user_content = (
                f"Step {index + 1}: {step}"
                if not prior_context
                else f"{prior_context}\n\nStep {index + 1}: {step}"
            )
            messages = [
                {"role": "system", "content": type(self)._step_system},
                {"role": "user", "content": user_content},
            ]
            raw = await llm.chat(messages=messages)
            result = self._extract_text(raw)
            step_results.append(result)
        combined = "\n".join(f"Step {i + 1}: {r}" for i, r in enumerate(step_results))
        return AgentResponse(content=combined)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
        return str(raw)
