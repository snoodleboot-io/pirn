"""``ToolNotFoundError`` — no registered tool matched the requested name."""

from __future__ import annotations

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class ToolNotFoundError(ToolInvocationError):
    """Raised when a :class:`ToolCall` names a tool absent from the registry.

    The message names the missing tool so the failure is actionable.

    Parameters
    ----------
    tool_name:
        The unresolved tool name requested by the call.
    call_id:
        Identifier of the originating tool call, or ``None``.
    """

    def __init__(self, tool_name: str, call_id: str | None = None) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' not found", call_id)
