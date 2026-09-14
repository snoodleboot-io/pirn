"""``Planner`` — produce an ordered :class:`Plan` from a :class:`ConversationPayload`.

Algorithm:
    1. Receive the resolved ``ConversationPayload`` and ``LLMProvider``.
    2. Validate input types at process time.
    3. Build a wire-format message list with the planning instruction + context messages.
    4. Call ``llm.chat`` with the messages.
    5. Extract text from the raw response.
    6. Parse lines: lines starting with ``#`` become rationale; numbered/bullet lines become steps.
    7. Raise ``ValueError`` if no steps were produced.
    8. Return a ``Plan`` with the ordered steps and rationale.


References:
    - :class:`pirn_agents.llm.llm_provider.LLMProvider`
    - :class:`pirn_agents.planning.plan.Plan`
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents._internal.json_shape import JsonShape
from pirn_agents.agent.recorded_llm_call import RecordedLlmCall
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.planning.plan import Plan
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.types.messaging.conversation_payload import ConversationPayload


class Planner(Knot):
    """Asks an :class:`LLMProvider` for a plan grounded in ``context``.

    The LLM response is expected to be plain text with one step per
    line. Lines starting with ``#`` are accumulated as the plan's
    rationale; everything else becomes a step.
    """

    #: Registry binding backing :attr:`planning_instruction`; see ``prompt/PROMPTS.md``.
    _planning_instruction: ClassVar[PromptBinding] = PromptBinding(
        name="planning.planner.planning_instruction",
        default=(
            "You are a planning assistant. Given the conversation so far, "
            "produce a numbered list of concrete steps the agent should "
            "take next. One step per line. Lines starting with '#' are "
            "treated as rationale and may explain your reasoning."
        ),
    )

    #: System prompt sent to the LLM. Override on a subclass to customise the
    #: planning instruction; a subclass value takes precedence over any
    #: registered/loaded template.
    planning_instruction: ClassVar[str] = _planning_instruction.default

    def __init__(
        self,
        *,
        context: Knot,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            context=context,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        context: ConversationPayload,
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
            ValueError: If the LLM response produces no plan steps.
        """
        wire_messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": type(self)._planning_instruction.resolve(
                    type(self).planning_instruction
                ),
            }
        ]
        for message in context.data:
            wire_messages.append({"role": message.role, "content": message.content})
        response = await RecordedLlmCall.chat(
            knot_id=self.knot_id, llm=llm, messages=tuple(wire_messages)
        )
        text = self._extract_text(response)
        return self._parse_plan(text)

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        text = self._text_from_mapping(response)
        if text is not None:
            return text
        raise TypeError(
            f"Planner: cannot extract text from LLM response of type {type(response).__name__}"
        )

    def _text_from_mapping(self, response: Any) -> str | None:
        """Return the text carried by a chat-completion mapping, or ``None``."""
        if not JsonShape.is_dict(response):
            return None
        content = response.get("content")
        if isinstance(content, str):
            return content
        if JsonShape.is_list(content) and content:
            first = content[0]
            if JsonShape.is_dict(first):
                text = first.get("text")
                if isinstance(text, str):
                    return text
        return None

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
            raise ValueError("Planner: LLM response produced no plan steps")
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
