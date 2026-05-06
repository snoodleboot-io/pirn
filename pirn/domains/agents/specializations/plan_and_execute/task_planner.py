"""``TaskPlanner`` — decomposes a goal into an ordered list of steps.

Algorithm:
    1. Receive the resolved ``goal`` (str) and ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Build a two-message request: system planning instruction + user goal.
    4. Call ``llm.chat`` with the messages and extract the raw text response.
    5. Parse lines that begin with a digit followed by ``.`` or ``)`` as steps.
    6. Return a Plan containing the ordered steps and the raw response as rationale.


References:
    - Wang et al. (2023) "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning"
    - Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.plan import Plan


class TaskPlanner(Knot):
    """Call the LLM with a planning prompt and return a :class:`Plan`.

    The LLM is asked to decompose the given goal into numbered steps. Lines
    starting with a digit followed by ``.`` or ``)`` are extracted as steps;
    blank lines and non-step lines are ignored. The full LLM response is
    stored as the plan's rationale.
    """

    _planning_system: str = (
        "You are an expert planner. Decompose the goal below into a numbered "
        "list of clear, actionable steps. Use the format:\n"
        "1. <first step>\n2. <second step>\n..."
    )

    def __init__(
        self,
        *,
        goal: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(goal=goal, llm=llm, _config=_config, **kwargs)

    async def process(self, goal: str, llm: LLMProvider, **_: Any) -> Plan:
        """Decompose the goal into an ordered plan via LLM and return a Plan.

        Args:
            goal: The high-level goal string to be decomposed into steps.

        Returns:
            A Plan containing the ordered step strings and the raw LLM rationale.

        Raises:
            TypeError: If goal is not a string.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"TaskPlanner: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(goal, str):
            raise TypeError(f"TaskPlanner: goal must be a string, got {type(goal).__name__}")
        messages = [
            {"role": "system", "content": type(self)._planning_system},
            {"role": "user", "content": goal},
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
