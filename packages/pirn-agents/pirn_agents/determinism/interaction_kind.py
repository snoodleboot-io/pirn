"""``InteractionKind`` — classifies a recorded unit of non-deterministic I/O."""

from __future__ import annotations

from enum import Enum


class InteractionKind(str, Enum):  # noqa: UP042 - str-mixin for stable serialisation
    """The class of external call a cassette entry captures.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    LLM:
        A model/chat completion call.
    TOOL:
        A tool invocation.
    RETRIEVAL:
        A memory/vector/retrieval call.
    GENERIC:
        Any other recorded I/O boundary.
    """

    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    GENERIC = "generic"
