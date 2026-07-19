"""Shared helper: pull plain text out of a provider chat-completion mapping.

Every F8 pattern knot needs the same normalisation from the provider-neutral
``LLMProvider.chat`` return value (a ``str`` or a ``{"content": ...}`` mapping,
possibly with a list of ``{"text": ...}`` blocks) down to a plain ``str``. This
module centralises that so each pattern does not re-implement it.
"""

from __future__ import annotations

from typing import Any


class LlmResponseText:
    """Normalise a provider chat-completion value down to plain text."""

    def extract(self, raw: Any) -> str:
        """Return the plain-text body of a chat-completion response.

        Args:
            raw: The value returned by ``LLMProvider.chat`` — a plain string, or a
                mapping whose ``"content"`` is either a string or a list of blocks
                each carrying a ``"text"`` field.

        Returns:
            The extracted text, or ``str(raw)`` as a last resort when no known
            shape matches.
        """
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
