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
