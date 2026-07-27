"""``AgentNestingConfig`` — the single source for agent-as-tool recursion limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class AgentNestingConfig(PirnOpaqueValue):
    """One place to declare how deep agent-as-tool nesting may go.

    An agent-as-tool call travels a fixed chain —
    :meth:`~pirn_agents.tools.agent_as_tool_mixin.AgentAsToolMixin.as_tool` →
    :func:`~pirn_agents.tools.as_tool.as_tool` →
    :class:`~pirn_agents.tools.agent_tool.AgentTool` →
    :class:`~pirn_agents.agent.agent_invoker.AgentInvoker` →
    :class:`~pirn_agents.agent.agent_tool_context.AgentToolContext` — and every
    link used to re-declare the same recursion cap as its own literal. Five
    copies of one safety limit is five chances for them to drift apart, and a
    lower cap deeper in the chain silently wins. The class-level field default
    here is the one declaration each link now reads (the same idiom
    :class:`~pirn_agents.specializations.document_processing._document_source_reader._DocumentSourceReader`
    uses for its byte cap), so the whole chain moves together.

    A frozen value rather than a module constant so a caller can also hand a
    *different* posture around as data — and so the limit is auditable.

    Attributes
    ----------
    max_depth:
        Maximum number of agent-as-tool frames that may be active at once. Must
        be >= 1. Defaults to 8, the chain's historical cap.
    """

    max_depth: int = 8

    def __post_init__(self) -> None:
        """Validate the recursion cap.

        Raises:
            ValueError: If ``max_depth`` is not an int >= 1.
        """
        if (
            isinstance(self.max_depth, bool)
            or not isinstance(self.max_depth, int)
            or self.max_depth < 1
        ):
            raise ValueError(
                f"AgentNestingConfig: max_depth must be an int >= 1, got {self.max_depth!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"max_depth": self.max_depth}
