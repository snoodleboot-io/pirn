"""High-level agent builder / DX facade (F19).

A thin, ergonomic layer over the knot-first API. The declarative
:class:`~pirn_agents.builder.agent_spec.AgentSpec`, the fluent
:class:`~pirn_agents.builder.agent_builder.AgentBuilder` (reached via
:class:`~pirn_agents.builder.agent.Agent`), and the curated
:class:`~pirn_agents.builder.agent_presets.AgentPresets` all *generate*
ordinary :class:`~pirn.nodes.sub_tapestry.SubTapestry` knot graphs. Nothing
is builder-only: every generated graph is identical to a hand-wired one, and
the underlying pattern classes stay directly constructible.

See ``BUILDER.md`` for the escape-hatch guide.
"""

from __future__ import annotations
