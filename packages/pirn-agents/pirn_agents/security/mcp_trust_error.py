"""``McpTrustError`` — a call was refused by the MCP trust policy."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class McpTrustError(PirnError, Exception):
    """Raised when the MCP trust policy refuses a server/tool call.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``Exception`` so every existing ``except Exception`` handler keeps
    working unchanged, while new code can narrow to ``PirnError``.

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
