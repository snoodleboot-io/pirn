"""Shared helper: pull plain text out of a provider chat-completion mapping.

Every knot that talks to an ``LLMProvider`` needs the same normalisation from
the provider-neutral ``LLMProvider.chat`` return value (a ``str`` or a
``{"content": ...}`` mapping, possibly with a list of ``{"text": ...}`` blocks)
down to a plain ``str``. This module centralises that so no call site
re-implements it.

A response matching none of those shapes raises
:class:`~pirn_agents.exceptions.unreadable_llm_response_error.UnreadableLlmResponseError`.
It used to ``return str(raw)``, which fabricated an answer: the repr of
whatever the provider sent became the RAG answer a user read, or the text a
fact extractor split into "facts" and wrote to long-term memory (PIR-873).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard

from pirn_agents.exceptions.unreadable_llm_response_error import (
    UnreadableLlmResponseError,
)


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
            The extracted text.

        Raises:
            UnreadableLlmResponseError: If *raw* matches none of those shapes.
                Never a fabricated ``str(raw)``: a response this code cannot
                read is a failure, not an answer.
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
        raise UnreadableLlmResponseError(raw)

    @staticmethod
    def _is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
        """Narrow a JSON-shaped value to a string-keyed mapping."""
        return isinstance(value, Mapping)

    @staticmethod
    def _is_block_list(value: object) -> TypeGuard[list[object]]:
        """Narrow a JSON-shaped ``content`` value to a list of blocks."""
        return isinstance(value, list)
