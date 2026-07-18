"""``AgentIntrospector`` — the one typed place agent dynamic-dispatch lives.

Running a nested agent needs two reflective probes over an otherwise opaque
agent object: a stable identity for cycle detection, and a check for whether the
agent's ``process`` accepts a given parameter. Both are inherently dynamic
(``getattr`` / :mod:`inspect`), so rather than scatter that reflection through
the invoker they are isolated here as a small, substitutable collaborator — the
single auditable home for the framework's agent introspection.
"""

from __future__ import annotations

import inspect


class AgentIntrospector:
    """Reflective probes over an agent object (isolates ``getattr`` / ``inspect``)."""

    def agent_key(self, agent: object) -> str:
        """Return a stable per-agent identity used for cycle detection.

        Prefers the agent's ``knot_id`` when it exposes a non-empty string one,
        falling back to a type-and-``id`` token so distinct instances never
        collide on the recursion stack.
        """
        knot_id = getattr(agent, "knot_id", None)
        if isinstance(knot_id, str) and knot_id:
            return knot_id
        return f"{type(agent).__name__}:{id(agent)}"

    def accepts_parameter(self, agent: object, name: str) -> bool:
        """Return whether the agent's ``process`` declares a parameter ``name``."""
        process = getattr(type(agent), "process", None)
        if process is None:
            return False
        try:
            signature = inspect.signature(process)
        except (TypeError, ValueError):
            return False
        return name in signature.parameters
