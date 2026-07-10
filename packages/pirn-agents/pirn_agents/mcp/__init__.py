"""Model Context Protocol (MCP) client and adapters (``[mcp]`` extra).

A first-class async MCP client so agents can consume any MCP server's tools,
resources, and prompts. The design is a thin JSON-RPC core
(:class:`McpClient`) driving a pluggable :class:`McpTransport` (real
:class:`StdioTransport` / :class:`StreamableHttpTransport`, or an in-memory
double), with adapters mapping the server's surface onto F1 primitives:
:class:`McpTool`/:class:`McpToolset` (→ ``Toolset``),
:class:`McpResourceAdapter` (→ context injection), and
:class:`McpPromptAdapter`/:class:`McpPromptTemplate` (→ message templates).
:class:`McpConnector` and :class:`McpSessionPool` vend one long-lived session
per server with reconnect/backoff.

The ``mcp`` backend is imported lazily (only when a concrete transport opens),
so ``import pirn_agents`` — and importing this subpackage — stays backend-free.
"""

from __future__ import annotations

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_connector import McpConnector
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_prompt_adapter import McpPromptAdapter
from pirn_agents.mcp.mcp_prompt_template import McpPromptTemplate
from pirn_agents.mcp.mcp_resource_adapter import McpResourceAdapter
from pirn_agents.mcp.mcp_session_pool import McpSessionPool
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.mcp.mcp_toolset import McpToolset
from pirn_agents.mcp.mcp_transport import McpTransport
from pirn_agents.mcp.stdio_transport import StdioTransport
from pirn_agents.mcp.streamable_http_transport import StreamableHttpTransport

__all__ = [
    "McpClient",
    "McpConnector",
    "McpError",
    "McpPromptAdapter",
    "McpPromptTemplate",
    "McpResourceAdapter",
    "McpSessionPool",
    "McpTool",
    "McpToolset",
    "McpTransport",
    "StdioTransport",
    "StreamableHttpTransport",
]
