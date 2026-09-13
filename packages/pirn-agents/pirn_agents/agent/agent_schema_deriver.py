"""``AgentSchemaDeriver`` — deprecated (one cycle); ``AgentTool.declaration()`` derives the schema.

Before the ADR "agents speaks core" (WS1) this class re-implemented the
annotation→JSON-Schema mapping for a ``SubTapestry`` agent's ``process``
signature.  An agent's caller-facing schema is now
``Knot.input_json_schema()`` minus the agent's bound inputs and injected
collaborators, rendered by :meth:`AgentTool.declaration`; :meth:`derive`
forwards there and warns.  The class will be removed next cycle.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.tools.agent_tool import AgentTool


class AgentSchemaDeriver:
    """Deprecated shim over :meth:`AgentTool.declaration`."""

    def __init__(self) -> None:
        warnings.warn(
            "AgentSchemaDeriver is deprecated (ADR agents-speaks-core WS1): use "
            "AgentTool(agent).declaration().parameters",
            DeprecationWarning,
            stacklevel=2,
        )

    def default_schema(self) -> dict[str, Any]:
        """Return the conventional single-``task`` schema for an input-less agent."""
        return AgentTool.default_schema()

    def derive(self, agent: object) -> Mapping[str, Any]:
        """Derive a JSON-Schema ``parameters`` object from ``agent``'s declared inputs."""
        if not isinstance(agent, SubTapestry):
            return self.default_schema()
        return AgentTool(agent).declaration().parameters
