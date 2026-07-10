"""``McpClient`` — a thin async JSON-RPC 2.0 core speaking Model Context Protocol.

OD-3 resolution: rather than depend on the official SDK for protocol logic, the
client implements the small slice of JSON-RPC that MCP needs — request/response
correlation by ``id``, notification dispatch, the ``initialize`` handshake with
capability negotiation, keep-alive ``ping``, and graceful shutdown. The optional
``mcp`` SDK is used only for real *transport* plumbing (behind
:class:`~pirn_agents.mcp.stdio_transport.StdioTransport` /
:class:`~pirn_agents.mcp.streamable_http_transport.StreamableHttpTransport`), so
the core stays dependency-light and fully exercisable with an in-memory transport
double.

The client is transport-agnostic: it drives any
:class:`~pirn_agents.mcp.mcp_transport.McpTransport`. It holds live connection
state, so it is a plain object (not a pirn opaque value); it is wrapped by
:class:`~pirn_agents.mcp.mcp_connector.McpConnector` when it must travel through
the graph.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_transport import McpTransport


class McpClient:
    """Drive an MCP server over a JSON-RPC transport with lifecycle management."""

    def __init__(
        self,
        transport: McpTransport,
        *,
        client_name: str = "pirn-agents",
        client_version: str = "0.9.0",
        protocol_version: str = "2025-06-18",
    ) -> None:
        """Bind the client to ``transport`` and record handshake identity.

        Args:
            transport: The frame carrier the client drives. Must be an
                :class:`McpTransport`.
            client_name: Name advertised to the server in ``initialize``.
            client_version: Version advertised to the server in ``initialize``.
            protocol_version: MCP protocol revision proposed during handshake.

        Raises:
            TypeError: If ``transport`` is not an :class:`McpTransport`.
        """
        if not isinstance(transport, McpTransport):
            raise TypeError(
                f"McpClient: transport must be an McpTransport, got {type(transport).__name__}"
            )
        self._transport: McpTransport = transport
        self._client_name: str = client_name
        self._client_version: str = client_version
        self._protocol_version: str = protocol_version
        self._next_id: int = 0
        self._initialized: bool = False
        self._server_capabilities: Mapping[str, Any] = {}
        self._server_info: Mapping[str, Any] = {}
        # Serialises send+receive per request so concurrent calls sharing one
        # vended session (S5) cannot interleave frames and mis-correlate by id.
        self._request_lock: asyncio.Lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        """Return whether the transport is live and the handshake completed."""
        return self._initialized and self._transport.is_open

    @property
    def server_capabilities(self) -> Mapping[str, Any]:
        """Return the capabilities the server advertised at ``initialize``."""
        return self._server_capabilities

    @property
    def server_info(self) -> Mapping[str, Any]:
        """Return the server's ``name``/``version`` info from ``initialize``."""
        return self._server_info

    async def open(self) -> None:
        """Open the transport and perform the ``initialize`` handshake.

        Sends ``initialize`` with the client's identity and capabilities,
        stores the negotiated server capabilities/info, then fires the
        ``notifications/initialized`` notification per the MCP lifecycle.
        Idempotent: a second call while already initialized is a no-op.

        Raises:
            McpError: If the server returns a JSON-RPC error to ``initialize``.
        """
        if self._initialized:
            return
        await self._transport.open()
        result = await self._request(
            "initialize",
            {
                "protocolVersion": self._protocol_version,
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "clientInfo": {"name": self._client_name, "version": self._client_version},
            },
        )
        capabilities = result.get("capabilities")
        self._server_capabilities = capabilities if isinstance(capabilities, Mapping) else {}
        info = result.get("serverInfo")
        self._server_info = info if isinstance(info, Mapping) else {}
        self._initialized = True
        await self._notify("notifications/initialized", {})

    async def aclose(self) -> None:
        """Close the transport and reset lifecycle state, idempotently.

        Named ``aclose`` so :class:`~pirn_agents.connector_base.ConnectorBase`
        awaits it during pooled teardown rather than calling a sync ``close``.
        """
        self._initialized = False
        await self._transport.close()

    async def ping(self) -> None:
        """Round-trip an MCP ``ping`` to keep the session alive / probe liveness.

        Raises:
            McpError: If the server returns an error to the ping.
        """
        await self._request("ping", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the server's tool descriptors (``name``/``description``/schema)."""
        result = await self._request("tools/list", {})
        return _as_dict_list(result.get("tools"))

    async def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Invoke server tool ``name`` with ``arguments`` and return the raw result.

        Args:
            name: The server tool's name.
            arguments: JSON-serialisable argument mapping for the tool.

        Returns:
            The raw MCP ``CallToolResult`` mapping (``content``/``isError``/
            optional ``structuredContent``).

        Raises:
            TypeError: If ``name`` is not a string or ``arguments`` not a Mapping.
            McpError: If the server returns a JSON-RPC error.
        """
        if not isinstance(name, str) or not name:
            raise TypeError(f"McpClient.call_tool: name must be a non-empty string, got {name!r}")
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"McpClient.call_tool: arguments must be a Mapping, got {type(arguments).__name__}"
            )
        return await self._request("tools/call", {"name": name, "arguments": dict(arguments)})

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return the server's resource descriptors (``uri``/``name``/...)."""
        result = await self._request("resources/list", {})
        return _as_dict_list(result.get("resources"))

    async def read_resource(self, uri: str) -> Mapping[str, Any]:
        """Read resource ``uri`` and return its raw ``contents`` mapping."""
        if not isinstance(uri, str) or not uri:
            raise TypeError(f"McpClient.read_resource: uri must be a non-empty string, got {uri!r}")
        return await self._request("resources/read", {"uri": uri})

    async def list_prompts(self) -> list[dict[str, Any]]:
        """Return the server's prompt descriptors (``name``/``arguments``/...)."""
        result = await self._request("prompts/list", {})
        return _as_dict_list(result.get("prompts"))

    async def get_prompt(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        """Fetch prompt ``name`` (optionally with ``arguments``) as a raw mapping."""
        if not isinstance(name, str) or not name:
            raise TypeError(f"McpClient.get_prompt: name must be a non-empty string, got {name!r}")
        params: dict[str, Any] = {"name": name}
        if arguments is not None:
            if not isinstance(arguments, Mapping):
                raise TypeError(
                    "McpClient.get_prompt: arguments must be a Mapping or None, "
                    f"got {type(arguments).__name__}"
                )
            params["arguments"] = dict(arguments)
        return await self._request("prompts/get", params)

    async def _request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        """Send a JSON-RPC request and return its correlated ``result`` mapping.

        Allocates the next monotonic ``id``, sends the request frame, then reads
        frames until the response whose ``id`` matches arrives — interleaved
        server notifications (no ``id``) and unrelated responses are skipped so
        the core tolerates a chatty server.

        Raises:
            McpError: If the matched response carries a JSON-RPC ``error``.
        """
        async with self._request_lock:
            self._next_id += 1
            request_id = self._next_id
            await self._transport.send(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params)}
            )
            while True:
                message = await self._transport.receive()
                if message.get("id") != request_id:
                    # A notification or a response to a different request; skip it.
                    continue
                error = message.get("error")
                if error is not None:
                    code = error.get("code") if isinstance(error, Mapping) else None
                    data = error.get("data") if isinstance(error, Mapping) else None
                    message_text = (
                        error.get("message") if isinstance(error, Mapping) else str(error)
                    )
                    raise McpError(
                        f"MCP {method!r} failed: {message_text}",
                        code=code if isinstance(code, int) else None,
                        data=data,
                    )
                result = message.get("result")
                return result if isinstance(result, Mapping) else {}

    async def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        """Send a fire-and-forget JSON-RPC notification (no ``id``, no reply)."""
        await self._transport.send({"jsonrpc": "2.0", "method": method, "params": dict(params)})


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Coerce a JSON-RPC list field into a list of plain dicts, dropping non-mappings."""
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
