"""``FinishReason`` — the neutral vocabulary for why generation stopped."""

from __future__ import annotations

from enum import Enum


class FinishReason(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Why the model stopped generating, in framework-neutral terms.

    String-valued for stable, human-readable serialisation independent of enum
    ordering, so the ~25 call sites constructing an
    :class:`~pirn_agents.types.messaging.agent_response.AgentResponse` with a
    bare ``"stop"`` keep working unchanged.

    These spellings are the *framework's* contract, not any vendor's. Every
    provider owns the translation from its own wire values onto this vocabulary
    and none is privileged: the chat-completions adapter maps ``tool_calls``
    here, the Messages adapter maps ``tool_use``, and the neutral member is
    whichever name reads best on its merits. A wire value outside a provider's
    known set is surfaced verbatim rather than coerced, so an unrecognised
    terminal stays visible instead of masquerading as a normal stop.

    Members
    -------
    STOP:
        Generation completed naturally. The only member
        :class:`~pirn_agents.control.termination_check.TerminationCheck` treats
        as terminal, and the default for a response that reports nothing.
    LENGTH:
        Generation was cut off by a token cap, so the reply is truncated.
    TOOL_USE:
        The model stopped to request one or more tool calls and expects their
        results before continuing.
    CONTENT_FILTER:
        Generation was halted by the provider's content policy.
    """

    STOP = "stop"
    LENGTH = "length"
    TOOL_USE = "tool_use"
    CONTENT_FILTER = "content_filter"
