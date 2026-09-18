"""Curated :class:`~pirn_agents.tools.toolset.Toolset` bundles for the base tools.

Factory methods on :class:`Bundles` group related base tools with sane
defaults so callers can register a whole capability with one line. Every
factory only *binds* tools — ``ReadFileTool.bind(root=...)`` — so no optional
backend (``httpx``, ``aiosqlite``) is imported here and importing this module
stays backend-free; a backend is imported lazily the first time a call that
needs it runs.


Example::

    from pirn_agents.tools.bundles import Bundles

    tools = Bundles.filesystem_toolset(root="/srv/workspace")
    react = ReActLoop(messages=msgs, llm=llm, tools=list(tools), _config=cfg)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
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
from pirn_agents.tools.sql.read_write_sql_query_tool import ReadWriteSqlQueryTool
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.toolset import Toolset
from pirn_agents.tools.web.html_to_text_tool import HtmlToTextTool
from pirn_agents.tools.web.http_request_tool import HttpRequestTool
from pirn_agents.tools.web.search_backend import SearchBackend
from pirn_agents.tools.web.web_search_tool import WebSearchTool


class Bundles:
    """Namespace of curated :class:`Toolset` factory methods."""

    @staticmethod
    def calculator_toolset() -> Toolset:
        """Return a toolset with the zero-dependency :class:`CalculatorTool`."""
        return Toolset([CalculatorTool])

    @staticmethod
    def web_toolset(
        *,
        search_backend: SearchBackend | None = None,
        fetch_tool: type[HttpRequestTool] = HttpRequestTool,
        max_bytes: int = 1_000_000,
        max_chars: int = 20_000,
        resolver: Callable[[str], str | Sequence[str]] | None = None,
    ) -> Toolset:
        """Return a web toolset: HTTP fetch, HTML-to-text, and optional web search.

        Args:
            search_backend: When provided, adds a :class:`WebSearchTool` over it;
                omitted (default) yields fetch + html-to-text only, so no search
                vendor is assumed.
            fetch_tool: The HTTP fetch capability to offer, which *is* the
                egress policy (PIR-817): :class:`HttpRequestTool` (default)
                reaches public hosts only,
                :class:`~pirn_agents.tools.web.private_http_request_tool.PrivateHttpRequestTool`
                may reach private/loopback addresses, and a deployment's own
                subclass narrows the hosts with ``_allowed_hosts``.  Neither the
                allowlist nor the private opt-in is an input any more, so no call
                the model writes can widen either.
            max_bytes: Response-body byte cap for HTTP fetch.
            max_chars: Output character cap for HTML-to-text.
            resolver: Optional DNS resolver forwarded to the fetch tool's SSRF guard.
        """
        tools: list[ToolFactory] = [
            fetch_tool.bind(max_bytes=max_bytes, resolver=resolver),
            HtmlToTextTool.bind(max_chars=max_chars),
        ]
        if search_backend is not None:
            tools.insert(0, WebSearchTool.bind(backend=search_backend))
        return Toolset(tools)

    @staticmethod
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
        tools: list[ToolFactory] = [
            ReadFileTool.bind(root=root, max_bytes=max_bytes),
            ListDirTool.bind(root=root, max_entries=max_entries),
            GlobTool.bind(root=root, max_results=max_entries),
        ]
        if include_write:
            tools.append(WriteFileTool.bind(root=root, max_bytes=max_bytes))
        return Toolset(tools)

    @staticmethod
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
            read_only: Which query capability to offer — ``True`` (default)
                gives the read-only :class:`SqlQueryTool`, ``False`` the
                write-enabled :class:`ReadWriteSqlQueryTool`.  The guard is the
                class, never a tool argument (PIR-817), so nothing in a call the
                model writes can turn a read into a write.
            max_rows: Row cap applied to query results.
            include_calculator: Also include :class:`CalculatorTool` (default ``True``).
        """
        query_tool: type[SqlQueryTool] = SqlQueryTool if read_only else ReadWriteSqlQueryTool
        tools: list[ToolFactory] = [query_tool.bind(connector=connector, max_rows=max_rows)]
        if include_calculator:
            tools.append(CalculatorTool.factory())
        return Toolset(tools)

    @staticmethod
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
        tools: list[ToolFactory] = [RetrieverTool.bind(store=store).defaults(top_k=top_k)]
        if llm is not None:
            tools.append(RagTool.bind(store=store, llm=llm).defaults(top_k=top_k))
        return Toolset(tools)

    @staticmethod
    def sandbox_toolset(*, executor: SandboxExecutor, include_shell: bool = True) -> Toolset:
        """Return a sandbox toolset backed by an (opt-in) :class:`SandboxExecutor`.

        The tools remain disabled unless ``executor`` was constructed with
        ``enabled=True`` (OD-1).

        Args:
            executor: The sandbox executor gating and running code/commands.
            include_shell: Also include :class:`ShellTool` (default ``True``).
        """
        tools: list[ToolFactory] = [PythonExecTool.bind(executor=executor)]
        if include_shell:
            tools.append(ShellTool.bind(executor=executor))
        return Toolset(tools)
