"""``StreamableHttpTransport`` — MCP JSON-RPC over streamable HTTP (``[mcp]`` extra).

Mirrors :class:`~pirn_agents.mcp.stdio_transport.StdioTransport` but drives a
remote server over the MCP streamable-HTTP transport instead of a subprocess.
The thin JSON-RPC core owns the protocol; this class owns only the HTTP session
plumbing, reusing the optional ``mcp`` SDK's ``streamablehttp_client``. Frames
are translated between the SDK's message object and the plain mappings the core
speaks. The backend is imported lazily via ``_require`` so importing this module
never pulls in ``mcp``.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AsyncExitStack
from typing import Any

from pirn_agents._require import _require
from pirn_agents.mcp.mcp_transport import McpTransport


class StreamableHttpTransport(McpTransport):
    """Carry MCP frames over a streamable-HTTP session to a remote server."""

    def __init__(
        self,
        *,
        url: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Describe the remote endpoint to connect to on :meth:`open`.

        Args:
            url: The MCP server's streamable-HTTP endpoint URL.
            headers: Optional headers (e.g. auth) sent on every request.

        Raises:
            TypeError: If ``url`` is not a non-empty string.
        """
        if not isinstance(url, str) or not url:
            raise TypeError(f"StreamableHttpTransport: url must be a non-empty string, got {url!r}")
        self._url: str = url
        self._headers: dict[str, str] | None = dict(headers) if headers is not None else None
        self._stack: AsyncExitStack | None = None
        self._read: Any | None = None
        self._write: Any | None = None

    @property
    def is_open(self) -> bool:
        """Return whether the HTTP session streams are currently established."""
        return self._read is not None and self._write is not None

    async def open(self) -> None:
        """Open the streamable-HTTP session and enter its stream context."""
        if self.is_open:
            return
        mcp = _require("mcp", "mcp")
        http = mcp.client.streamable_http  # type: ignore[attr-defined]
        stack = AsyncExitStack()
        streams = await stack.enter_async_context(
            http.streamablehttp_client(self._url, headers=self._headers)
        )
        # The streamable-HTTP client yields (read, write, get_session_id); the
        # core only needs the first two frame streams.
        read, write = streams[0], streams[1]
        self._stack = stack
        self._read = read
        self._write = write

    async def send(self, message: Mapping[str, Any]) -> None:
        """Serialise ``message`` to an SDK JSON-RPC object and write it."""
        if self._write is None:
            raise RuntimeError("StreamableHttpTransport.send: transport is not open")
        mcp = _require("mcp", "mcp")
        rpc = mcp.types.JSONRPCMessage.model_validate(dict(message))  # type: ignore[attr-defined]
        await self._write.send(_wrap_session_message(mcp, rpc))

    async def receive(self) -> Mapping[str, Any]:
        """Read the next SDK frame and normalise it to a plain mapping."""
        if self._read is None:
            raise RuntimeError("StreamableHttpTransport.receive: transport is not open")
        frame = await self._read.receive()
        return _frame_to_mapping(frame)

    async def close(self) -> None:
        """Exit the session context and drop references, idempotently."""
        stack = self._stack
        self._stack = None
        self._read = None
        self._write = None
        if stack is not None:
            await stack.aclose()


def _wrap_session_message(mcp: Any, rpc: Any) -> Any:
    """Wrap a ``JSONRPCMessage`` in a ``SessionMessage`` when the SDK expects one."""
    session_message = getattr(mcp.types, "SessionMessage", None)
    if session_message is not None:
        return session_message(message=rpc)
    return rpc


def _frame_to_mapping(frame: Any) -> Mapping[str, Any]:
    """Convert an SDK stream frame (``SessionMessage`` or ``JSONRPCMessage``) to a dict."""
    if isinstance(frame, BaseException):
        raise frame
    message = getattr(frame, "message", frame)
    dumped = message.model_dump(by_alias=True, mode="json", exclude_none=True)
    return dict(dumped)
