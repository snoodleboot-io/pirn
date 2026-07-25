"""``McpTrustError`` — a call was refused by the MCP trust policy."""

from __future__ import annotations


class McpTrustError(Exception):
    """Raised when the MCP trust policy refuses a server/tool call.

    Parameters
    ----------
    message:
        Human-readable reason for the refusal.
    server:
        The MCP server name the call targeted, or ``None``.
    tool:
        The tool name the call targeted, or ``None``.
    """

    def __init__(self, message: str, *, server: str | None = None, tool: str | None = None) -> None:
        self.message = message
        self.server = server
        self.tool = tool
        super().__init__(message)
