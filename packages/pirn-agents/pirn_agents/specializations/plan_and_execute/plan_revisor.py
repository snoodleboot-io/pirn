"""``PlanRevisor`` — revises a failed plan given partial results and failure reason.

Algorithm:
    1. Receive the resolved ``original_plan`` (Plan), ``completed_results`` (str),
       ``failure_reason`` (str), and ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Format the original steps and completed results into a structured user message.
    4. Call ``llm.chat`` with a revision system prompt and the user message.
    5. Parse the numbered-list response into a revised list of remaining steps.
    6. Return a new Plan with the revised steps and the raw LLM response as rationale.


References:
    - Wang et al. (2023) "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning"
    - Shinn et al. (2023) "Reflexion: Language Agents with Verbal Reinforcement Learning"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.types.plan import Plan


class PlanRevisor(Knot):
    """On task failure, produce a revised remaining plan via LLM.

    Given the original plan, the completed step results so far, and the
    failure reason, the LLM is asked to produce a revised list of remaining
    steps. The same numbered-list parsing as :class:`TaskPlanner` is applied
    to extract the revised steps.
    """

    _revision_system: str = (
        "You are an expert planner. A task plan has partially failed. "
        "Given the original plan, the completed results so far, and the "
        "failure reason, produce a revised numbered list of remaining steps "
        "to recover and complete the goal. Use the format:\n"
        "1. <first remaining step>\n2. <second remaining step>\n..."
    )

    def __init__(
        self,
        *,
        original_plan: Knot,
        completed_results: Knot | str,
        failure_reason: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_plan=original_plan,
            completed_results=completed_results,
            failure_reason=failure_reason,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_plan: Plan,
        completed_results: str,
        failure_reason: str,
        llm: LLMProvider,
        **_: Any,
    ) -> Plan:
        """Revise the remaining plan based on completed results and failure reason.

        Args:
            original_plan: The Plan that was being executed when failure occurred.
            completed_results: A string summary of results from completed steps.
            failure_reason: A description of why the plan failed.

        Returns:
            A revised Plan containing the remaining steps to complete the goal.

        Raises:
            TypeError: If original_plan is not a Plan instance.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"PlanRevisor: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(original_plan, Plan):
            raise TypeError(
                f"PlanRevisor: original_plan must be a Plan, got {type(original_plan).__name__}"
            )
        original_steps_text = "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(original_plan.steps)
        )
        user_content = (
            f"Original plan:\n{original_steps_text}\n\n"
            f"Completed results:\n{completed_results}\n\n"
            f"Failure reason:\n{failure_reason}"
        )
        messages = [
            {"role": "system", "content": type(self)._revision_system},
            {"role": "user", "content": user_content},
        ]
        raw = await llm.chat(messages=messages)
        rationale = self._extract_text(raw)
        steps = self._parse_steps(rationale)
        return Plan(steps=tuple(steps), rationale=rationale)

    @staticmethod
    def _parse_steps(text: str) -> list[str]:
        steps: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) >= 2 and stripped[0].isdigit() and stripped[1] in ".)":
                step = stripped[2:].strip()
                if step:
                    steps.append(step)
        return steps

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
