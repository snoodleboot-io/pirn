"""Shared helper: pull plain text out of a provider chat-completion mapping.

Every F8 pattern knot needs the same normalisation from the provider-neutral
``LLMProvider.chat`` return value (a ``str`` or a ``{"content": ...}`` mapping,
possibly with a list of ``{"text": ...}`` blocks) down to a plain ``str``. This
module centralises that so each pattern does not re-implement it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard


class LlmResponseText:
    """Normalise a provider chat-completion value down to plain text."""

    def extract(self, raw: object) -> str:
        """Return the plain-text body of a chat-completion response.

        Args:
            raw: The value returned by ``LLMProvider.chat`` — a plain string, or a
                mapping whose ``"content"`` is a string or a list of blocks (each a
                string or a mapping carrying a ``"text"`` field), or a mapping with a
                top-level ``"text"`` string.

        Returns:
            The extracted text, or ``str(raw)`` as a last resort when no known
            shape matches.
        """
        if isinstance(raw, str):
            return raw
        if LlmResponseText._is_mapping(raw):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if LlmResponseText._is_block_list(content) and content:
                first = content[0]
                if LlmResponseText._is_mapping(first):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)

    @staticmethod
    def _is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
        """Narrow a JSON-shaped value to a string-keyed mapping."""
        return isinstance(value, Mapping)

    @staticmethod
    def _is_block_list(value: object) -> TypeGuard[list[object]]:
        """Narrow a JSON-shaped ``content`` value to a list of blocks."""
        return isinstance(value, list)
