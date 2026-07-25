"""``TraceEventKind`` — the kind of step a :class:`TraceEvent` records."""

from __future__ import annotations

from enum import Enum


class TraceEventKind(str, Enum):  # noqa: UP042 - str-mixin for stable serialisation
    """Classifies one step in a captured run trajectory.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    INPUT:
        An input handed to the run (prompt, query, arguments).
    DECISION:
        A control-flow / planning decision the agent made.
    LLM_CALL:
        A model/chat completion call.
    TOOL_CALL:
        A tool invocation request.
    TOOL_RESULT:
        The result returned by a tool.
    RETRIEVAL:
        A memory/vector/retrieval call.
    OUTPUT:
        A produced output of the run.
    """

    INPUT = "input"
    DECISION = "decision"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRIEVAL = "retrieval"
    OUTPUT = "output"
