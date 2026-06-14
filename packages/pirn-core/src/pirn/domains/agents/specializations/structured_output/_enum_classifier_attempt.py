"""``_EnumClassifierAttempt`` — internal helper Knot for :class:`EnumClassifierPipeline`.

Single LLM call: builds the classification prompt, parses the LLM reply,
and returns the matched label or raises :class:`ValueError` when no
label matches. Internal API.

Algorithm:
    1. Receive ``prompt`` (string) and ``labels`` (sequence of allowed labels).
    2. Build a system message instructing the LLM to choose exactly one label.
    3. Call the LLM provider with the system + user chat messages.
    4. Extract text from the raw LLM response.
    5. Match the text exactly, then case-insensitively, against the label set.
    6. Return the matched label, or raise :class:`ValueError` on no match.


References:
    - :class:`pirn.core.providers.llm_provider.LLMProvider`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider


class _EnumClassifierAttempt(Knot):
    """Single LLM call: prompt, parse the reply, return the matched label."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        labels: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, labels=labels, _config=_config, **kwargs)

    async def process(self, prompt: str, llm: LLMProvider, labels: Sequence[str], **_: Any) -> str:
        """Ask the LLM to choose one label from the allowed set and return the matched label.

        Args:
            prompt: The classification prompt string sent to the LLM as a user message.
            llm: The LLM provider to call.
            labels: The sequence of allowed label strings.

        Returns:
            The matched label string from the allowed set.

        Raises:
            TypeError: If prompt is not a string.
            ValueError: If the LLM reply does not match any allowed label.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"EnumClassifierPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        labels_tuple = tuple(labels)
        lower_index = {label.lower(): label for label in labels_tuple}
        system_message = (
            "You are a classifier. Choose exactly one label from the list "
            f"{list(labels_tuple)!r}. Reply with the label only — no "
            "punctuation, prose, or quoting."
        )
        chat_messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        raw = await llm.chat(chat_messages)
        text = self._extract_text(raw).strip()
        for label in labels_tuple:
            if text == label:
                return label
        match = lower_index.get(text.lower())
        if match is not None:
            return match
        raise ValueError(
            "EnumClassifierPipeline: model returned "
            f"{text!r} which is not in the allowed labels "
            f"{list(labels_tuple)!r}"
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
