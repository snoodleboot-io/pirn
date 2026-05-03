"""``Planner`` — produce an ordered :class:`Plan` from an :class:`AgentContext`."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.plan import Plan


class Planner(Knot):
    """Asks an :class:`LLMProvider` for a plan grounded in ``context``.

    The LLM response is expected to be plain text with one step per
    line. Lines starting with ``#`` are accumulated as the plan's
    rationale; everything else becomes a step.
    """

    planning_instruction: ClassVar[str] = (
        "You are a planning assistant. Given the conversation so far, "
        "produce a numbered list of concrete steps the agent should "
        "take next. One step per line. Lines starting with '#' are "
        "treated as rationale and may explain your reasoning."
    )

    def __init__(
        self,
        *,
        context: Knot,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "Planner: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        super().__init__(
            context=context,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        context: AgentContext,
        llm: LLMProvider,
        **_: Any,
    ) -> Plan:
        """Ask the LLM to produce a step-by-step Plan grounded in the agent context.

        Args:
            context: The agent context providing the conversation history for planning.
            llm: LLM provider used to generate the plan.

        Returns:
            A Plan containing the ordered steps and optional rationale.

        Raises:
            TypeError: If context is not an AgentContext instance.
            ValueError: If the LLM response produces no plan steps.
        """
        if not isinstance(context, AgentContext):
            raise TypeError(
                "Planner: context must be an AgentContext, "
                f"got {type(context).__name__}"
            )
        wire_messages: list[dict[str, str]] = [
            {"role": "system", "content": type(self).planning_instruction}
        ]
        for message in context.messages:
            wire_messages.append(
                {"role": message.role, "content": message.content}
            )
        response = await llm.chat(messages=tuple(wire_messages))
        text = self._extract_text(response)
        return self._parse_plan(text)

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            content = response.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]
        raise TypeError(
            "Planner: cannot extract text from LLM response of type "
            f"{type(response).__name__}"
        )

    def _parse_plan(self, text: str) -> Plan:
        rationale_lines: list[str] = []
        step_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                rationale_lines.append(stripped.lstrip("#").strip())
                continue
            cleaned = self._strip_leading_enumerator(stripped)
            if cleaned:
                step_lines.append(cleaned)
        if not step_lines:
            raise ValueError(
                "Planner: LLM response produced no plan steps"
            )
        return Plan(
            steps=tuple(step_lines),
            rationale="\n".join(rationale_lines),
        )

    def _strip_leading_enumerator(self, line: str) -> str:
        head, _, rest = line.partition(".")
        if head.isdigit() and rest:
            return rest.strip()
        if line.startswith(("- ", "* ")):
            return line[2:].strip()
        return line
