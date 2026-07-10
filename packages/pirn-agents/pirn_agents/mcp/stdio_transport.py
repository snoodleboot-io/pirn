"""``StdioTransport`` — MCP JSON-RPC over a stdio subprocess (``[mcp]`` extra).

The thin JSON-RPC core (:class:`~pirn_agents.mcp.mcp_client.McpClient`) owns the
protocol; this transport owns only the *plumbing* — spawning the server process
and moving frames over its stdin/stdout. It uses the optional ``mcp`` SDK's
low-level ``stdio_client`` for the subprocess + framing (the piece worth reusing)
and translates each frame between the SDK's message object and the plain
mappings the core speaks. The backend is imported lazily via ``_require`` so
``import pirn_agents`` — and even importing this module — never pulls in ``mcp``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AsyncExitStack
from typing import Any

from pirn_agents._require import _require
from pirn_agents.mcp.mcp_transport import McpTransport


class StdioTransport(McpTransport):
    """Carry MCP frames over a spawned stdio server subprocess."""

    def __init__(
        self,
        *,
        command: str,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Describe the server subprocess to spawn on :meth:`open`.

        Args:
            command: Executable to launch (e.g. ``"python"``).
            args: Argument vector passed to ``command``.
            env: Environment overrides for the child process.

        Raises:
            TypeError: If ``command`` is not a non-empty string.
        """
        if not isinstance(command, str) or not command:
            raise TypeError(f"StdioTransport: command must be a non-empty string, got {command!r}")
        self._command: str = command
        self._args: list[str] = list(args or ())
        self._env: dict[str, str] | None = dict(env) if env is not None else None
        self._stack: AsyncExitStack | None = None
        self._read: Any | None = None
        self._write: Any | None = None

    @property
    def is_open(self) -> bool:
        """Return whether the subprocess streams are currently established."""
        return self._read is not None and self._write is not None

    async def open(self) -> None:
        """Spawn the server and enter its stdio stream context."""
        if self.is_open:
            return
        mcp = _require("mcp", "mcp")
        stdio = mcp.client.stdio  # type: ignore[attr-defined]
        params = stdio.StdioServerParameters(command=self._command, args=self._args, env=self._env)
        stack = AsyncExitStack()
        read, write = await stack.enter_async_context(stdio.stdio_client(params))
        self._stack = stack
        self._read = read
        self._write = write

    async def send(self, message: Mapping[str, Any]) -> None:
        """Serialise ``message`` to an SDK JSON-RPC object and write it."""
        if self._write is None:
            raise RuntimeError("StdioTransport.send: transport is not open")
        mcp = _require("mcp", "mcp")
        rpc = mcp.types.JSONRPCMessage.model_validate(dict(message))  # type: ignore[attr-defined]
        await self._write.send(_wrap_session_message(mcp, rpc))

    async def receive(self) -> Mapping[str, Any]:
        """Read the next SDK frame and normalise it to a plain mapping."""
        if self._read is None:
            raise RuntimeError("StdioTransport.receive: transport is not open")
        frame = await self._read.receive()
        return _frame_to_mapping(frame)

    async def close(self) -> None:
        """Exit the stream context and drop references, idempotently."""
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
