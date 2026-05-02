"""``LLMChatCall`` — single :meth:`LLMProvider.chat` request.

A thin wrapper around :meth:`LLMProvider.chat` that takes a single
prompt string, frames it as a one-shot user message, and returns the
text content extracted from the provider's response. Used inside RAG
specializations where the upstream knots produce a fully-formed prompt
string and the downstream knots need a string answer.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class LLMChatCall(Knot):
    """Calls :meth:`LLMProvider.chat` and returns the assistant text."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "LLMChatCall: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if max_tokens is not None and (
            not isinstance(max_tokens, int) or max_tokens <= 0
        ):
            raise ValueError(
                "LLMChatCall: max_tokens must be a positive int or None, "
                f"got {max_tokens!r}"
            )
        if temperature is not None and not isinstance(
            temperature, (int, float)
        ):
            raise ValueError(
                "LLMChatCall: temperature must be a number or None, "
                f"got {temperature!r}"
            )
        self._llm = llm
        self._system = system
        self._max_tokens = max_tokens
        self._temperature = (
            float(temperature) if temperature is not None else None
        )
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> str:
        if not isinstance(prompt, str):
            raise TypeError(
                "LLMChatCall: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        chat_messages: list[dict[str, Any]] = []
        if self._system:
            chat_messages.append({"role": "system", "content": self._system})
        chat_messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {}
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        response = await self._llm.chat(chat_messages, **kwargs)
        return self._extract_text(response)

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
