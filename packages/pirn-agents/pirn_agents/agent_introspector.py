"""``AgentIntrospector`` — the one typed place agent dynamic-dispatch lives.

Running a nested agent needs two reflective probes over an otherwise opaque
agent object: a stable identity for cycle detection, and a check for whether the
agent's ``process`` accepts a given parameter. Both dispatch on
``isinstance(agent, Knot)`` — the declared agent base — before reading the
``knot_id`` / ``process`` members it guarantees, with :mod:`inspect` used only
to read the signature. Rather than scatter that reflection through the invoker it
is isolated here as a small, substitutable collaborator — the single auditable
home for the framework's agent introspection.
"""

from __future__ import annotations

import inspect

from pirn.core.knot import Knot


class AgentIntrospector:
    """Reflective probes over an agent object (dispatches on ``isinstance(Knot)``)."""

    def agent_key(self, agent: object) -> str:
        """Return a stable per-agent identity used for cycle detection.

        Prefers the agent's ``knot_id`` when it exposes a non-empty string one,
        falling back to a type-and-``id`` token so distinct instances never
        collide on the recursion stack.
        """
        if isinstance(agent, Knot) and agent.knot_id:
            return agent.knot_id
        return f"{type(agent).__name__}:{id(agent)}"

    def accepts_parameter(self, agent: object, name: str) -> bool:
        """Return whether the agent's ``process`` declares a parameter ``name``."""
        if not isinstance(agent, Knot):
            return False
        try:
            signature = inspect.signature(type(agent).process)
        except (TypeError, ValueError):
            return False
        return name in signature.parameters
