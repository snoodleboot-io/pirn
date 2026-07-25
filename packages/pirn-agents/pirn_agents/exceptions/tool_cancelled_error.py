"""``ToolCancelledError`` — a tool invocation was cancelled before completing."""

from __future__ import annotations

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class ToolCancelledError(ToolInvocationError):
    """Raised when a tool invocation is cancelled before it completes.

    The message names the cancelled tool.

    Parameters
    ----------
    tool_name:
        Name of the tool whose invocation was cancelled.
    call_id:
        Identifier of the originating tool call, or ``None``.
    """

    def __init__(self, tool_name: str, call_id: str | None = None) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' was cancelled", call_id)
