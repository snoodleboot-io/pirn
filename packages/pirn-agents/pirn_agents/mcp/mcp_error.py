"""``McpError`` — a Model Context Protocol JSON-RPC / lifecycle failure."""

from __future__ import annotations

from typing import Any


class McpError(Exception):
    """Raised when an MCP exchange fails at the protocol or transport layer.

    Carries the JSON-RPC error ``code`` and optional ``data`` payload when the
    failure originated from a server-returned JSON-RPC error object, so callers
    can react programmatically as well as read the human-readable message.

    Parameters
    ----------
    message:
        Human-readable description of the failure.
    code:
        JSON-RPC error code when the failure is a server error object, else
        ``None`` (e.g. a transport drop or a reconnect exhaustion).
    data:
        Provider-supplied error data payload, or ``None``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        data: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code: int | None = code
        self.data: Any | None = data
