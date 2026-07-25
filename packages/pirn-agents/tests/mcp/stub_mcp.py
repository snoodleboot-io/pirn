"""In-memory MCP doubles shared by the mcp mirrored tests.

``StubMcpTransport`` is a fake JSON-RPC peer: it records every frame the client
sends and, for each request, synthesises the matching response from a table of
per-method handlers — no real MCP server, no subprocess, no sockets. It can also
inject an interleaved notification before a response (to prove the client's
id-correlation skips it) and fail a configurable number of ``open`` calls (to
drive reconnect/backoff). ``build_default_server`` returns a small but complete
handler table covering tools, resources, and prompts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pirn_agents.mcp.mcp_transport import McpTransport

Handler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class StubMcpTransport(McpTransport):
    """A scripted in-memory JSON-RPC peer for driving :class:`McpClient`."""

    def __init__(
        self,
        *,
        handlers: Mapping[str, Handler] | None = None,
        fail_opens: int = 0,
        notify_before_response: bool = False,
    ) -> None:
        self._handlers: dict[str, Handler] = dict(handlers or build_default_server())
        self._fail_opens = fail_opens
        self._notify_before_response = notify_before_response
        self._open = False
        self._outbox: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []
        self.opens = 0
        self.closes = 0

    @property
    def is_open(self) -> bool:
        return self._open

    async def open(self) -> None:
        self.opens += 1
        if self._fail_opens > 0:
            self._fail_opens -= 1
            raise ConnectionError("stub transport: open failed")
        self._open = True

    async def send(self, message: Mapping[str, Any]) -> None:
        self.sent.append(dict(message))
        if "id" not in message:
            return  # a notification; no response is produced
        if self._notify_before_response:
            # An unrelated server notification the client must skip by id.
            self._outbox.append({"jsonrpc": "2.0", "method": "notifications/message", "params": {}})
        method = str(message.get("method", ""))
        handler = self._handlers.get(method)
        params = message.get("params", {})
        response: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        if handler is None:
            response["error"] = {"code": -32601, "message": f"method not found: {method}"}
        else:
            produced = handler(params if isinstance(params, Mapping) else {})
            if "__error__" in produced:
                response["error"] = produced["__error__"]
            else:
                response["result"] = dict(produced)
        self._outbox.append(response)

    async def receive(self) -> Mapping[str, Any]:
        if not self._outbox:
            raise ConnectionError("stub transport: nothing to receive")
        return self._outbox.pop(0)

    async def close(self) -> None:
        self.closes += 1
        self._open = False


def build_default_server() -> dict[str, Handler]:
    """Return a complete handler table for a small canned MCP server."""

    def initialize(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "stub-server", "version": "1.0"},
        }

    def ping(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    def tools_list(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo the given text back.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
                {
                    "name": "add",
                    "description": "Add two integers, returning structured content.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    },
                },
                {
                    "name": "boom",
                    "description": "Always reports an error.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {"description": "a nameless tool that must be skipped"},
            ]
        }

    def tools_call(params: Mapping[str, Any]) -> Mapping[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "echo":
            return {"content": [{"type": "text", "text": arguments.get("text", "")}]}
        if name == "add":
            total = int(arguments.get("a", 0)) + int(arguments.get("b", 0))
            return {
                "content": [{"type": "text", "text": str(total)}],
                "structuredContent": {"sum": total},
            }
        if name == "boom":
            return {"content": [{"type": "text", "text": "kaboom"}], "isError": True}
        return {"__error__": {"code": -32602, "message": f"unknown tool: {name}"}}

    def resources_list(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "resources": [
                {"uri": "file:///a.txt", "name": "a"},
                {"uri": "file:///b.txt", "name": "b"},
            ]
        }

    def resources_read(params: Mapping[str, Any]) -> Mapping[str, Any]:
        uri = params.get("uri", "")
        if uri == "file:///malformed":
            return {"contents": "not-a-list"}
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"content of {uri}"}]}

    def prompts_list(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "prompts": [
                {
                    "name": "greet",
                    "description": "Greet a person in a language.",
                    "arguments": [
                        {"name": "name", "description": "person", "required": True},
                        {"name": "lang", "description": "language", "required": False},
                    ],
                }
            ]
        }

    def prompts_get(_params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "description": "Greet a person in a language.",
            "messages": [
                {"role": "system", "content": {"type": "text", "text": "Respond in {lang}."}},
                {"role": "user", "content": {"type": "text", "text": "Hello {name}!"}},
            ],
        }

    return {
        "initialize": initialize,
        "ping": ping,
        "tools/list": tools_list,
        "tools/call": tools_call,
        "resources/list": resources_list,
        "resources/read": resources_read,
        "prompts/list": prompts_list,
        "prompts/get": prompts_get,
    }


async def open_stub_client(**kwargs: Any) -> Any:
    """Build an :class:`McpClient` over a default stub transport and open it."""
    from pirn_agents.mcp.mcp_client import McpClient

    transport = StubMcpTransport(**kwargs)
    client = McpClient(transport)
    await client.open()
    return client
