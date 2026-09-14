"""Shared helper: pull plain text out of a provider chat-completion mapping.

Every F8 pattern knot needs the same normalisation from the provider-neutral
``LLMProvider.chat`` return value (a ``str`` or a ``{"content": ...}`` mapping,
possibly with a list of ``{"text": ...}`` blocks) down to a plain ``str``. This
module centralises that so each pattern does not re-implement it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class LlmResponseText:
    """Normalise a provider chat-completion value down to plain text."""

    def extract(self, raw: Mapping[str, Any] | str) -> str:
        """Return the plain-text body of a chat-completion response.

        Args:
            raw: The value returned by ``LLMProvider.chat`` — a plain string, or a
                mapping whose ``"content"`` is either a string or a list of blocks
                each carrying a ``"text"`` field.

        Returns:
            The extracted text, or ``str(raw)`` as a last resort when no known
            shape matches.
        """
        match raw:
            case str():
                return raw
            case {"content": str() as content}:
                return content
            case {"content": [{"text": str() as text}, *_]}:
                return text
            case _:
                return str(raw)
