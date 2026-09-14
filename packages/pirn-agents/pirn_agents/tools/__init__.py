"""Base tool library — concrete, production-grade :class:`Tool` implementations.

The ``pirn_agents.tools`` package ships the "batteries" for the batteries-
included agent runtime: web, filesystem, calculator, SQL, sandboxed code
execution, and retrieval/RAG tools, plus curated :class:`~pirn_agents.tools.toolset.Toolset`
bundles that group them with sane defaults.

Every tool derives from :class:`~pirn_agents.tools.tool.Tool` directly, so it
exposes a provider-neutral JSON schema (``declaration()``) and returns a typed
F1 :class:`~pirn_agents.tools.tool_result.ToolResult` via
:meth:`~pirn_agents.tools.tool_result.ToolResult.from_result`. Optional
backends (``httpx`` for web, ``aiosqlite`` for async SQL) are imported lazily at
call time, so importing this package stays backend-free.
"""

from __future__ import annotations
