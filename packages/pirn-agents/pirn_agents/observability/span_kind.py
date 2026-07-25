"""``SpanKind`` — the kind of operation a :class:`Span` wraps."""

from __future__ import annotations

from enum import Enum


class SpanKind(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Classifies a span by the call site it instruments.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    LLM:
        A model/chat completion call.
    TOOL:
        A tool invocation.
    RETRIEVAL:
        A memory/vector retrieval call.
    GENERIC:
        Any other instrumented region.
    """

    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    GENERIC = "generic"
