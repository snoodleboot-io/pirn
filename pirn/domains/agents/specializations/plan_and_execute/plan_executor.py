"""``PlanExecutor`` — executes each step of a Plan sequentially via LLM calls."""

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
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "PlanExecutor: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(plan=plan, _config=_config, **kwargs)

    async def process(self, plan: Plan, **_: Any) -> AgentResponse:
        """Execute each plan step sequentially and return an AgentResponse with all outputs.

        Args:
            plan: The Plan whose steps will be executed in order.

        Returns:
            An AgentResponse whose content contains each step result separated by newlines.

        Raises:
            TypeError: If plan is not a Plan instance.
        """
        if not isinstance(plan, Plan):
            raise TypeError(
                "PlanExecutor: plan must be a Plan, "
                f"got {type(plan).__name__}"
            )
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
            raw = await self._llm.chat(messages=messages)
            result = self._extract_text(raw)
            step_results.append(result)
        combined = "\n".join(
            f"Step {i + 1}: {r}" for i, r in enumerate(step_results)
        )
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
