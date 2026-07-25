"""Curated :class:`~pirn_agents.toolset.Toolset` bundles for the base tools.

Factory functions that group related base tools with sane defaults so callers can
register a whole capability with one line. Every factory only *constructs* tools —
no optional backend (``httpx``, ``aiosqlite``) is imported here, so importing this
module stays backend-free; a backend is imported lazily the first time a tool that
needs it is invoked.

Example::

    from pirn_agents.tools.bundles import filesystem_toolset

    tools = filesystem_toolset(root="/srv/workspace")
    react = ReActLoop(messages=msgs, llm=llm, tools=list(tools), _config=cfg)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.tool import Tool
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.tools.filesystem.glob_tool import GlobTool
from pirn_agents.tools.filesystem.list_dir_tool import ListDirTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.filesystem.write_file_tool import WriteFileTool
from pirn_agents.tools.retrieval.rag_tool import RagTool
from pirn_agents.tools.retrieval.retriever_tool import RetrieverTool
from pirn_agents.tools.sandbox.python_exec_tool import PythonExecTool
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.sandbox.shell_tool import ShellTool
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.web.html_to_text_tool import HtmlToTextTool
from pirn_agents.tools.web.http_request_tool import HttpRequestTool
from pirn_agents.tools.web.search_backend import SearchBackend
from pirn_agents.tools.web.web_search_tool import WebSearchTool
from pirn_agents.toolset import Toolset


def calculator_toolset() -> Toolset:
    """Return a toolset with the zero-dependency :class:`CalculatorTool`."""
    return Toolset([CalculatorTool()])


def web_toolset(
    *,
    search_backend: SearchBackend | None = None,
    allowed_hosts: tuple[str, ...] | None = None,
    allow_private: bool = False,
    max_bytes: int = 1_000_000,
    max_chars: int = 20_000,
    resolver: Callable[[str], str | Sequence[str]] | None = None,
) -> Toolset:
    """Return a web toolset: HTTP fetch, HTML-to-text, and optional web search.

    Args:
        search_backend: When provided, adds a :class:`WebSearchTool` over it;
            omitted (default) yields fetch + html-to-text only, so no search
            vendor is assumed.
        allowed_hosts: Optional host allow-list applied to HTTP fetches.
        allow_private: Opt-in to allow private/loopback fetch targets.
        max_bytes: Response-body byte cap for HTTP fetch.
        max_chars: Output character cap for HTML-to-text.
        resolver: Optional DNS resolver forwarded to the fetch tool's SSRF guard.
    """
    tools: list[Tool] = [
        HttpRequestTool(
            allowed_hosts=allowed_hosts,
            allow_private=allow_private,
            max_bytes=max_bytes,
            resolver=resolver,
        ),
        HtmlToTextTool(max_chars=max_chars),
    ]
    if search_backend is not None:
        tools.insert(0, WebSearchTool(backend=search_backend))
    return Toolset(tools)


def filesystem_toolset(
    *,
    root: str,
    max_bytes: int = 1_000_000,
    max_entries: int = 1000,
    include_write: bool = True,
) -> Toolset:
    """Return a filesystem toolset scoped to ``root``.

    Args:
        root: Root directory every tool is confined to.
        max_bytes: Read/write byte cap.
        max_entries: Listing/glob result cap.
        include_write: When ``False``, omit :class:`WriteFileTool` for a
            read-only filesystem view.
    """
    tools: list[Tool] = [
        ReadFileTool(root=root, max_bytes=max_bytes),
        ListDirTool(root=root, max_entries=max_entries),
        GlobTool(root=root, max_results=max_entries),
    ]
    if include_write:
        tools.append(WriteFileTool(root=root, max_bytes=max_bytes))
    return Toolset(tools)


def data_toolset(
    *,
    connector: SqlConnector,
    read_only: bool = True,
    max_rows: int = 1000,
    include_calculator: bool = True,
) -> Toolset:
    """Return a data toolset: a guarded ``sql_query`` plus an optional calculator.

    Args:
        connector: The SQL connector the query tool delegates to.
        read_only: Enforce read-only SQL (default ``True``).
        max_rows: Row cap applied to query results.
        include_calculator: Also include :class:`CalculatorTool` (default ``True``).
    """
    tools: list[Tool] = [SqlQueryTool(connector=connector, read_only=read_only, max_rows=max_rows)]
    if include_calculator:
        tools.append(CalculatorTool())
    return Toolset(tools)


def retrieval_toolset(
    *,
    store: MemoryStore,
    llm: LLMProvider | None = None,
    top_k: int = 5,
) -> Toolset:
    """Return a retrieval toolset: a retriever plus an optional RAG tool.

    Args:
        store: The memory store both tools search.
        llm: When provided, adds a :class:`RagTool` composing retrieval + this LLM.
        top_k: Default result count for both tools.
    """
    tools: list[Tool] = [RetrieverTool(store=store, top_k=top_k)]
    if llm is not None:
        tools.append(RagTool(store=store, llm=llm, top_k=top_k))
    return Toolset(tools)


def sandbox_toolset(*, executor: SandboxExecutor, include_shell: bool = True) -> Toolset:
    """Return a sandbox toolset backed by an (opt-in) :class:`SandboxExecutor`.

    The tools remain disabled unless ``executor`` was constructed with
    ``enabled=True`` (OD-1).

    Args:
        executor: The sandbox executor gating and running code/commands.
        include_shell: Also include :class:`ShellTool` (default ``True``).
    """
    tools: list[Tool] = [PythonExecTool(executor=executor)]
    if include_shell:
        tools.append(ShellTool(executor=executor))
    return Toolset(tools)
