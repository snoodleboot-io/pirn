"""``Agent`` — the top-level entry point to the high-level builder facade.

``Agent`` is a thin, stateless facade over the one authoring spine:
:meth:`Agent.builder` starts a fresh
:class:`~pirn_agents.builder.agent_builder.AgentBuilder` (the fluent way in),
:meth:`Agent.from_spec` configures one from a declarative
:class:`~pirn_agents.builder.agent_spec.AgentSpec` (the config-driven way in),
and :meth:`Agent.patterns` reports the pattern names both understand. Nothing
here is required to use the knot-first API — it is purely an ergonomic front
door that generates ordinary knot graphs.
"""

from __future__ import annotations

from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.agent_references import AgentReferences
from pirn_agents.builder.agent_spec import AgentSpec


class Agent:
    """Entry point for the high-level agent builder facade."""

    @classmethod
    def builder(cls) -> AgentBuilder:
        """Return a fresh :class:`AgentBuilder` to fluently configure an agent."""
        return AgentBuilder()

    @classmethod
    def from_spec(cls, spec: AgentSpec, *, references: AgentReferences) -> AgentBuilder:
        """Return an :class:`AgentBuilder` configured from a declarative spec.

        The config-driven door onto the same spine the fluent API uses: the
        result is an ordinary builder, so ``.input(...).build()`` finishes it
        and every escape-hatch accessor still applies.

        Args:
            spec: The declarative description to configure from.
            references: Table mapping the spec's reference labels to the live
                objects they stand for.

        Returns:
            A configured :class:`AgentBuilder`, ready for ``.input(...).build()``.
        """
        return AgentBuilder.from_spec(spec, references=references)

    @classmethod
    def patterns(cls) -> tuple[str, ...]:
        """Return the pattern names the builder can generate."""
        return AgentPatternRegistry.pattern_names()
