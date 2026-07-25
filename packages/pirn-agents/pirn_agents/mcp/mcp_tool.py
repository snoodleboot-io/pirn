"""``McpTool`` — adapt one discovered MCP server tool to the F1 ``Tool`` protocol.

An :class:`McpTool` wraps a single tool descriptor discovered from an MCP server
(its ``name``, ``description``, and JSON-Schema ``inputSchema``) and delegates
:meth:`invoke` to the server's ``tools/call``. The raw MCP ``CallToolResult`` is
mapped to a plain Python value so the tool composes with F1's
:class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor`, which wraps
the return in a :class:`~pirn_agents.types.tool_result.ToolResult`. For direct
(executor-free) use, :meth:`as_tool_result` produces the ``ToolResult`` itself so
schema *and* result round-trip through F1's protocol either way.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class McpTool(Tool):
    """A remote MCP tool exposed through the local :class:`Tool` interface."""

    def __init__(
        self,
        *,
        client: McpClient,
        name: str,
        description: str = "",
        parameters_schema: Mapping[str, Any] | None = None,
    ) -> None:
        """Bind a discovered MCP tool descriptor to a live client.

        Args:
            client: The :class:`McpClient` whose session backs invocations.
            name: The server tool's stable name.
            description: Human-readable description shown to the planner.
            parameters_schema: The tool's JSON-Schema for arguments; defaults to
                an empty-object schema when the server omits one.

        Raises:
            TypeError: If ``client`` is not an :class:`McpClient` or ``name`` is
                not a non-empty string.
        """
        if not isinstance(client, McpClient):
            raise TypeError(f"McpTool: client must be an McpClient, got {type(client).__name__}")
        if not isinstance(name, str) or not name:
            raise TypeError(f"McpTool: name must be a non-empty string, got {name!r}")
        self._client: McpClient = client
        self._name: str = name
        self._description: str = description
        self._parameters_schema: Mapping[str, Any] = (
            dict(parameters_schema)
            if isinstance(parameters_schema, Mapping)
            else {"type": "object", "properties": {}}
        )

    @classmethod
    def from_descriptor(cls, *, client: McpClient, descriptor: Mapping[str, Any]) -> McpTool:
        """Build an :class:`McpTool` from a ``tools/list`` descriptor mapping.

        Args:
            client: The client whose session backs invocations.
            descriptor: One entry from :meth:`McpClient.list_tools`.

        Raises:
            TypeError: If ``descriptor`` is not a Mapping or lacks a valid name.
        """
        if not isinstance(descriptor, Mapping):
            raise TypeError(
                f"McpTool.from_descriptor: descriptor must be a Mapping, "
                f"got {type(descriptor).__name__}"
            )
        return cls(
            client=client,
            name=descriptor.get("name", ""),
            description=descriptor.get("description", ""),
            parameters_schema=descriptor.get("inputSchema"),
        )

    @property
    def name(self) -> str:
        """Return the tool's stable server name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the tool's human-readable description."""
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the tool's JSON-Schema argument specification."""
        return self._parameters_schema

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Call the remote tool and return its result mapped to a plain value.

        Args:
            arguments: Argument mapping conforming to :attr:`parameters_schema`.

        Returns:
            The mapped MCP result (structured content, a string, or a list).

        Raises:
            TypeError: If ``arguments`` is not a Mapping.
            McpError: If the server marks the result as an error (``isError``)
                or returns a JSON-RPC error.
        """
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"McpTool.invoke: arguments must be a Mapping, got {type(arguments).__name__}"
            )
        raw = await self._client.call_tool(self._name, arguments)
        if raw.get("isError") is True:
            raise McpError(f"MCP tool {self._name!r} reported an error: {_result_text(raw)}")
        return _map_tool_result(raw)

    async def as_tool_result(self, call: ToolCall) -> ToolResult:
        """Invoke for ``call`` and return a fully-formed F1 :class:`ToolResult`.

        A server-reported error becomes a ``ToolStatus.ERROR`` result rather than
        a raised exception, so callers get the same terminal shape F1's executor
        would produce.

        Args:
            call: The originating :class:`ToolCall`; its ``call_id`` is echoed.

        Raises:
            TypeError: If ``call`` is not a :class:`ToolCall`.
        """
        if not isinstance(call, ToolCall):
            raise TypeError(
                f"McpTool.as_tool_result: call must be a ToolCall, got {type(call).__name__}"
            )
        start = time.perf_counter()
        try:
            raw = await self._client.call_tool(self._name, call.arguments)
        except McpError as exc:
            return ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=str(exc),
                latency=time.perf_counter() - start,
            )
        latency = time.perf_counter() - start
        if raw.get("isError") is True:
            return ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=f"MCP tool {self._name!r} reported an error: {_result_text(raw)}",
                latency=latency,
            )
        return ToolResult(
            call_id=call.call_id,
            result=_map_tool_result(raw),
            status=ToolStatus.OK,
            latency=latency,
        )

    def _clear_credentials(self) -> None:
        """Drop the client reference so any held session becomes GC-able."""
        self._client = None  # type: ignore[assignment]


def _map_tool_result(raw: Mapping[str, Any]) -> Any:
    """Map an MCP ``CallToolResult`` mapping to a plain Python value.

    Structured content wins when present; otherwise text blocks are unwrapped —
    a single text block to its string, several to a list, non-text blocks kept as
    their raw dicts so nothing is silently lost.
    """
    structured = raw.get("structuredContent")
    if isinstance(structured, Mapping):
        return dict(structured)
    content = raw.get("content")
    if not isinstance(content, list):
        return None
    mapped: list[Any] = []
    for block in content:
        if isinstance(block, Mapping) and block.get("type") == "text":
            mapped.append(block.get("text", ""))
        elif isinstance(block, Mapping):
            mapped.append(dict(block))
    if len(mapped) == 1:
        return mapped[0]
    return mapped


def _result_text(raw: Mapping[str, Any]) -> str:
    """Join an MCP result's text blocks for a readable error message."""
    content = raw.get("content")
    if not isinstance(content, list):
        return ""
    parts = [
        str(block.get("text", ""))
        for block in content
        if isinstance(block, Mapping) and block.get("type") == "text"
    ]
    return " ".join(parts)
