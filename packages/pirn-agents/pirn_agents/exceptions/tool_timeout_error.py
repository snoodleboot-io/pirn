"""``ToolTimeoutError`` — a tool invocation exceeded its time budget."""

from __future__ import annotations

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class ToolTimeoutError(ToolInvocationError):
    """Raised when a tool invocation exceeds its allotted time budget.

    The message names the tool and the ``timeout`` it overran.

    Parameters
    ----------
    tool_name:
        Name of the tool whose invocation timed out.
    timeout:
        The elapsed-time budget, in seconds, that was exceeded.
    call_id:
        Identifier of the originating tool call, or ``None``.
    """

    def __init__(self, tool_name: str, timeout: float, call_id: str | None = None) -> None:
        self.tool_name = tool_name
        self.timeout = timeout
        super().__init__(f"Tool '{tool_name}' timed out after {timeout}s", call_id)
