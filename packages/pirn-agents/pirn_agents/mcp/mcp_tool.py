"""``McpTool`` — one discovered MCP server tool as a schema-declared tool capability.

An MCP server advertises a tool as a descriptor — ``name``, ``description``
and a JSON-Schema ``inputSchema`` — with no Python signature to introspect.
That is exactly the case core's ``KnotFactory.from_schema`` exists for (ADR
agents-speaks-core, WS0/WS1): the schema is the input contract, each property
becomes the ``TypeAdapter`` ``validate_io`` applies, and ``process`` receives
the validated arguments by keyword.  ``McpTool`` is the
:class:`~pirn_agents.tools.tool_factory.ToolFactory` over such a generated
:class:`~pirn_agents.tools.tool.Tool` subclass, whose ``process()`` delegates
to the server's ``tools/call`` through the bound :class:`McpClient` and maps
the raw ``CallToolResult`` to a plain Python value.  One call is one knot:
``factory.for_call(call)``; the engine records its ``Result``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.json_shape import JsonShape
from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.tools.tool_factory import ToolFactory


class McpTool(ToolFactory):
    """A remote MCP tool exposed as a local tool capability."""

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
            client: The :class:`McpClient` whose session backs every call.
            name: The server tool's stable name.
            description: Human-readable description shown to the planner.
            parameters_schema: The tool's JSON-Schema for arguments; defaults to
                an empty-object schema when the server omits one.

        Raises:
            TypeError: If ``client`` is not an :class:`McpClient`, ``name`` is
                not a non-empty string, or the schema is not an object schema
                core can declare inputs from.
        """
        if not isinstance(client, McpClient):
            raise TypeError(f"McpTool: client must be an McpClient, got {type(client).__name__}")
        if not isinstance(name, str) or not name:
            raise TypeError(f"McpTool: name must be a non-empty string, got {name!r}")
        schema: Mapping[str, Any] = (
            dict(parameters_schema)
            if JsonShape.is_mapping(parameters_schema)
            else {"type": "object", "properties": {}}
        )
        self._client: McpClient | None = client
        self._remote_name = name
        knot_class = ToolFactory.schema_declared_class(
            f"McpTool_{name}",
            schema,
            self._call_remote,
            description=description,
            tool_name=name,
        )
        super().__init__(knot_class, name=name, description=description)

    @classmethod
    def from_descriptor(cls, *, client: McpClient, descriptor: Mapping[str, Any]) -> McpTool:
        """Build an :class:`McpTool` from a ``tools/list`` descriptor mapping.

        Args:
            client: The client whose session backs invocations.
            descriptor: One entry from :meth:`McpClient.list_tools`.

        Raises:
            TypeError: If ``descriptor`` is not a Mapping or lacks a valid name.
        """
        if not JsonShape.is_mapping(descriptor):
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

    async def _call_remote(self, **arguments: Any) -> Any:
        """The generated knot's body: ``tools/call`` on the server, mapped to a value.

        Raises:
            McpError: If the server marks the result as an error (``isError``),
                returns a JSON-RPC error, or the client has been cleared.
        """
        if self._client is None:
            raise McpError(f"MCP tool {self._remote_name!r} has no client (credentials cleared)")
        raw = await self._client.call_tool(self._remote_name, arguments)
        if raw.get("isError") is True:
            raise McpError(
                f"MCP tool {self._remote_name!r} reported an error: {McpTool._result_text(raw)}"
            )
        return McpTool._map_tool_result(raw)

    def _clear_credentials(self) -> None:
        """Drop the client reference so any held session becomes GC-able."""
        self._client = None

    @staticmethod
    def _map_tool_result(raw: Mapping[str, Any]) -> Any:
        """Map an MCP ``CallToolResult`` mapping to a plain Python value.

        Structured content wins when present; otherwise text blocks are
        unwrapped — a single text block to its string, several to a list,
        non-text blocks kept as their raw dicts so nothing is silently lost.
        """
        structured = raw.get("structuredContent")
        if JsonShape.is_mapping(structured):
            return dict(structured)
        content = raw.get("content")
        if not JsonShape.is_list(content):
            return None
        mapped: list[Any] = []
        for block in content:
            if JsonShape.is_mapping(block) and block.get("type") == "text":
                mapped.append(block.get("text", ""))
            elif JsonShape.is_mapping(block):
                mapped.append(dict(block))
        if len(mapped) == 1:
            return mapped[0]
        return mapped

    @staticmethod
    def _result_text(raw: Mapping[str, Any]) -> str:
        """Join an MCP result's text blocks for a readable error message."""
        content = raw.get("content")
        if not JsonShape.is_list(content):
            return ""
        parts = [
            str(block.get("text", ""))
            for block in content
            if JsonShape.is_mapping(block) and block.get("type") == "text"
        ]
        return " ".join(parts)
