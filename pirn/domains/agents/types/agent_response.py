"""The final (or intermediate) response surfaced by an agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.agents.types.tool_call import ToolCall


@dataclass(frozen=True)
class AgentResponse(PirnOpaqueValue):
    """Outcome of one agent turn.

    Attributes
    ----------
    content:
        Free-form textual reply.
    tool_calls:
        Tuple of :class:`ToolCall`s the agent wants to dispatch before
        producing a final answer. Empty when the agent has nothing to
        defer.
    finish_reason:
        Reason the model stopped generating (``"stop"``, ``"length"``,
        ``"tool_use"``, etc.). Defaults to ``"stop"``.
    usage:
        Mapping of token-usage fields (e.g. ``input_tokens``,
        ``output_tokens``) returned by the provider. Defaults to an
        empty dict.
    """

    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str = "stop"
    usage: Mapping[str, int] = field(default_factory=dict)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [t._pirn_audit_dict() for t in self.tool_calls],
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
        }
