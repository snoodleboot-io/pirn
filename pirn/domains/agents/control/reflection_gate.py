"""``ReflectionGate`` — LLM-driven decision on whether to iterate again."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class ReflectionGate(Knot):
    """Asks an :class:`LLMProvider` whether the agent should iterate again.

    The LLM is prompted to answer ``yes`` (iterate) or ``no``
    (terminate). The chat-completion mapping is interrogated for plain
    text; a leading ``yes`` / ``y`` counts as ``True``. Anything else
    returns ``False``.
    """

    reflection_prompt: ClassVar[str] = (
        "You are an agent reflection assistant. Given the response "
        "below, decide whether the agent should iterate again to "
        "improve it. Answer 'yes' to iterate or 'no' to stop. Reply "
        "with the single word only."
    )

    def __init__(
        self,
        *,
        response: Knot,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ReflectionGate: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        super().__init__(
            response=response,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        llm: LLMProvider,
        **_: Any,
    ) -> bool:
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "ReflectionGate: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        wire_messages = (
            {"role": "system", "content": type(self).reflection_prompt},
            {"role": "user", "content": response.content},
        )
        raw = await llm.chat(messages=wire_messages)
        text = self._extract_text(raw)
        normalised = text.strip().lower()
        return normalised.startswith("yes") or normalised.startswith("y ")

    def _extract_text(self, raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]
        raise TypeError(
            "ReflectionGate: cannot extract text from response of type "
            f"{type(raw).__name__}"
        )
