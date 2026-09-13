"""``SpanKind`` — the kind of operation a :class:`Span` wraps.

.. deprecated:: ADR agents-speaks-core WS4a
    Part of the deprecated Tracer/Span plane; scheduled for deletion after one
    release cycle. The replacement,
    :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`,
    takes the equivalent ``kind`` as a plain string (``"llm"``/``"tool"``/
    ``"retrieval"``) in its ``extra`` mapping instead of a dedicated enum.
"""

from __future__ import annotations

from enum import Enum


class SpanKind(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Classifies a span by the call site it instruments.

    .. deprecated:: ADR agents-speaks-core WS4a
        See the module docstring.

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
