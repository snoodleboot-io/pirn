"""``ClarificationRequester`` — detect ambiguity and generate a clarifying question.

A :class:`Knot` that asks an LLM whether the user's message is
ambiguous. If the LLM judges it ambiguous, it generates and returns a
clarifying question. If the message is clear, the original message is
returned unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class ClarificationRequester(Knot):
    """Detect ambiguity via LLM and return a clarifying question or the original message."""

    def __init__(
        self,
        *,
        message: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ClarificationRequester: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(message=message, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        **_: Any,
    ) -> str:
        """Detect whether the message is ambiguous and return a clarifying question or the original.

        Args:
            message: The user message to evaluate for ambiguity.

        Returns:
            A clarifying question string if ambiguous, otherwise the original message.

        Raises:
            TypeError: If message is not a string.
        """
        if not isinstance(message, str):
            raise TypeError(
                "ClarificationRequester: message must be a string, "
                f"got {type(message).__name__}"
            )
        prompt = (
            "You are evaluating whether a user message is ambiguous.\n"
            "If the message is clear and unambiguous, reply with exactly: CLEAR\n"
            "If the message is ambiguous, reply with a single clarifying question.\n\n"
            f"Message: {message}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        response_text = self._extract_text(raw).strip()
        if response_text.upper() == "CLEAR":
            return message
        return response_text

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
