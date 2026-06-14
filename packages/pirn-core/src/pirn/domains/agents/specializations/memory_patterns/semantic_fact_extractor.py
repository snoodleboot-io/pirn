"""``SemanticFactExtractor`` — extract discrete factual claims via an LLM.

Inner stage knot used by :class:`SemanticMemoryPipeline`. Renders the
trailing conversation as a single user prompt prefixed with the
caller-supplied ``fact_extraction_prompt``, parses the LLM's reply into
a list of facts (one per non-empty line, with leading list markers
stripped), and returns the extracted facts.

Algorithm
---------
1. Validate inputs.
2. Render messages as ``role: content`` lines.
3. Prepend ``fact_extraction_prompt`` and call the LLM.
4. Parse the reply line-by-line, stripping list markers.
5. Return the list of non-empty fact strings.

Math
----
No mathematical operations.

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_message import AgentMessage


class SemanticFactExtractor(Knot):
    """Calls an :class:`LLMProvider` and parses out a list of fact strings."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        llm: Knot | LLMProvider,
        fact_extraction_prompt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            llm=llm,
            fact_extraction_prompt=fact_extraction_prompt,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        llm: LLMProvider,
        fact_extraction_prompt: str,
        **_: Any,
    ) -> list[str]:
        """Ask the LLM to extract factual claims from the conversation and return them as a list.

        Args:
            messages: The sequence of agent messages forming the conversation to analyse.
            llm: The LLMProvider to query for fact extraction.
            fact_extraction_prompt: Non-empty prompt string prefixed to the conversation.

        Returns:
            A list of factual claim strings extracted from the conversation.

        Raises:
            TypeError: If llm is not an LLMProvider.
            ValueError: If fact_extraction_prompt is not a non-empty string.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SemanticFactExtractor: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(fact_extraction_prompt, str) or not fact_extraction_prompt:
            raise ValueError(
                "SemanticFactExtractor: fact_extraction_prompt must be a non-empty string"
            )
        message_tuple = tuple(messages)
        rendered = "\n".join(f"{m.role}: {m.content}" for m in message_tuple)
        prompt = (
            f"{fact_extraction_prompt}\n\nConversation:\n{rendered}\n\nReturn one fact per line."
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await llm.chat(chat_messages)
        text = self._extract_text(raw)
        facts: list[str] = []
        for raw_line in text.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker) :].strip()
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
