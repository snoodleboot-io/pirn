"""``_EnumClassifierAttempt`` — internal helper Knot for :class:`EnumClassifierPipeline`.

Single LLM call: builds the classification prompt, parses the LLM reply,
and returns the matched label or raises :class:`ValueError` when no
label matches. Internal API.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class _EnumClassifierAttempt(Knot):
    """Single LLM call: prompt, parse the reply, return the matched label."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        labels: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._labels = tuple(labels)
        self._lower_index = {label.lower(): label for label in self._labels}
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> str:
        """Ask the LLM to choose one label from the allowed set and return the matched label.

        Args:
            prompt: The classification prompt string sent to the LLM as a user message.

        Returns:
            The matched label string from the allowed set.

        Raises:
            TypeError: If prompt is not a string.
            ValueError: If the LLM reply does not match any allowed label.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "EnumClassifierPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        system_message = (
            "You are a classifier. Choose exactly one label from the list "
            f"{list(self._labels)!r}. Reply with the label only — no "
            "punctuation, prose, or quoting."
        )
        chat_messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw).strip()
        for label in self._labels:
            if text == label:
                return label
        match = self._lower_index.get(text.lower())
        if match is not None:
            return match
        raise ValueError(
            "EnumClassifierPipeline: model returned "
            f"{text!r} which is not in the allowed labels "
            f"{list(self._labels)!r}"
        )

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
