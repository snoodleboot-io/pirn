"""Base tool library — concrete, production-grade :class:`Tool` implementations.

The ``pirn_agents.tools`` package ships the "batteries" for the batteries-
included agent runtime: web, filesystem, calculator, SQL, sandboxed code
execution, and retrieval/RAG tools, plus curated :class:`~pirn_agents.toolset.Toolset`
bundles that group them with sane defaults.

Every tool derives from :class:`~pirn_agents.tools.base_tool.BaseTool` (a thin
:class:`~pirn_agents.tool.Tool` subclass) so it exposes a provider-neutral JSON
schema and returns a typed F1 :class:`~pirn_agents.types.tool_result.ToolResult`
via :meth:`~pirn_agents.tools.base_tool.BaseTool.as_tool_result`. Optional
backends (``httpx`` for web, ``aiosqlite`` for async SQL) are imported lazily at
call time, so importing this package stays backend-free.
"""

from __future__ import annotations
