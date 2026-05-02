"""``SemanticFactExtractor`` — extract discrete factual claims via an LLM.

Inner stage knot used by :class:`SemanticMemoryPipeline`. Renders the
trailing conversation as a single user prompt prefixed with the
caller-supplied ``fact_extraction_prompt``, parses the LLM's reply into
a list of facts (one per non-empty line, with leading list markers
stripped), and returns the extracted facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_message import AgentMessage


class SemanticFactExtractor(Knot):
    """Calls an :class:`LLMProvider` and parses out a list of fact strings."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        llm: LLMProvider,
        fact_extraction_prompt: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SemanticFactExtractor: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if (
            not isinstance(fact_extraction_prompt, str)
            or not fact_extraction_prompt
        ):
            raise ValueError(
                "SemanticFactExtractor: fact_extraction_prompt must be a "
                "non-empty string"
            )
        self._llm = llm
        self._fact_prompt = fact_extraction_prompt
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> list[str]:
        message_tuple = tuple(messages)
        rendered = "\n".join(
            f"{m.role}: {m.content}" for m in message_tuple
        )
        prompt = (
            f"{self._fact_prompt}\n\n"
            "Conversation:\n"
            f"{rendered}\n\n"
            "Return one fact per line."
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw)
        facts: list[str] = []
        for raw_line in text.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker):].strip()
                    break
            if cleaned[:2].isdigit() and cleaned[:3].endswith("."):
                cleaned = cleaned[3:].strip()
            elif cleaned[:1].isdigit() and cleaned[:2].endswith("."):
                cleaned = cleaned[2:].strip()
            if cleaned:
                facts.append(cleaned)
        return facts

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
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
