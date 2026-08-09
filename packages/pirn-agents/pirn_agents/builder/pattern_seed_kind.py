"""``PatternSeedKind`` — how a pattern's runtime seed is coerced before binding."""

from __future__ import annotations

from enum import Enum


class PatternSeedKind(Enum):
    """Classifies the shape a pattern's seed parameter expects.

    The builder collects one runtime seed via ``.input(...)``. Most patterns
    take it verbatim; conversational ones take a tuple of
    :class:`~pirn_agents.types.messaging.agent_message.AgentMessage`, and accept
    a bare string as shorthand for a single ``user`` turn. This enum records
    which of the two a pattern is, so the coercion is declared per pattern
    rather than inferred from a parameter name.

    Values are the strings :meth:`PatternDescriptor.describe` reports, so a
    printed contract stays readable independent of enum ordering.

    Members
    -------
    VALUE:
        The seed is passed to the constructor unchanged.
    MESSAGES:
        The seed is normalised to a tuple of ``AgentMessage``; a bare string
        becomes a single ``user`` message.
    """

    VALUE = "value"
    MESSAGES = "messages"
