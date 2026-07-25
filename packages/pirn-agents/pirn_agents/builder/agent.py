"""``Agent`` — the top-level entry point to the high-level builder facade.

``Agent`` is a thin, stateless facade: :meth:`Agent.builder` starts a fresh
:class:`~pirn_agents.builder.agent_builder.AgentBuilder`, and
:meth:`Agent.patterns` reports the pattern names that builder understands.
Nothing here is required to use the knot-first API — it is purely an ergonomic
front door that generates ordinary knot graphs.
"""

from __future__ import annotations

from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry


class Agent:
    """Entry point for the high-level agent builder facade."""

    @classmethod
    def builder(cls) -> AgentBuilder:
        """Return a fresh :class:`AgentBuilder` to fluently configure an agent."""
        return AgentBuilder()

    @classmethod
    def patterns(cls) -> tuple[str, ...]:
        """Return the pattern names the builder can generate."""
        return AgentPatternRegistry.pattern_names()
