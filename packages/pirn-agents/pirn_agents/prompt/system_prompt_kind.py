"""``SystemPromptKind`` — the canonical roles a system-prompt layer can play."""

from __future__ import annotations

from enum import Enum


class SystemPromptKind(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """The canonical roles a :class:`SystemPromptLayer` can declare.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    *Declaration order is the composition order*: the rank a layer composes at
    is its position in this enum, so the vocabulary and the ordering cannot
    drift apart. The vocabulary is deliberately open — a layer may carry any
    non-empty ``kind`` string, and every kind outside this enum shares the
    single trailing rank returned by :meth:`rank_of`, composing after the
    canonical layers in first-seen order.

    Members
    -------
    PERSONA:
        Who the agent is — composed first so everything after it is read in
        character.
    POLICY:
        What the agent may and may not do; placed after the persona so rules
        constrain the character rather than the other way round.
    TOOLS:
        The tool surface available for this turn.
    MEMORY:
        Recalled context for this turn — composed last of the canonical kinds
        because it is the most volatile, which keeps the stable prefix intact
        for prompt caching.
    """

    PERSONA = "persona"
    POLICY = "policy"
    TOOLS = "tools"
    MEMORY = "memory"

    @classmethod
    def rank_of(cls, kind: str) -> int:
        """Return the canonical composition rank for a layer ``kind``.

        Args:
            kind: The layer's declared kind, canonical or custom.

        Returns:
            The member's zero-based declaration index, or the trailing rank
            (the member count) for any kind outside this vocabulary.
        """
        for rank, member in enumerate(cls):
            if member.value == kind:
                return rank
        return len(cls)
