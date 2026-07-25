"""``McpToolset`` — discover an MCP server's tools and build an F1 ``Toolset``.

Discovery calls ``tools/list`` through the client, wraps each descriptor in an
:class:`~pirn_agents.mcp.mcp_tool.McpTool`, and assembles them into an F1
:class:`~pirn_agents.toolset.Toolset` — the same ordered, uniquely-named registry
any knot accepts. :meth:`refresh` re-runs discovery so a long-lived agent can
pick up tools a server adds mid-run.
"""

from __future__ import annotations

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.toolset import Toolset


class McpToolset:
    """Populate an F1 :class:`Toolset` from an MCP server's advertised tools."""

    def __init__(self, *, client: McpClient) -> None:
        """Bind the toolset builder to a live client.

        Args:
            client: The :class:`McpClient` whose session backs discovery and the
                resulting tools' invocations.

        Raises:
            TypeError: If ``client`` is not an :class:`McpClient`.
        """
        if not isinstance(client, McpClient):
            raise TypeError(f"McpToolset: client must be an McpClient, got {type(client).__name__}")
        self._client: McpClient = client

    async def discover(self) -> Toolset:
        """List the server's tools and return them as an F1 :class:`Toolset`.

        Returns:
            A :class:`Toolset` with one :class:`McpTool` per advertised tool, in
            server order. Descriptors missing a name are skipped so one malformed
            entry does not abort discovery.
        """
        descriptors = await self._client.list_tools()
        tools = [
            McpTool.from_descriptor(client=self._client, descriptor=descriptor)
            for descriptor in descriptors
            if descriptor.get("name")
        ]
        return Toolset(tools)

    async def refresh(self) -> Toolset:
        """Re-run discovery and return a freshly-populated :class:`Toolset`."""
        return await self.discover()
