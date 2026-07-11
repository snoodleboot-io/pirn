"""Agentic Pipelines / Patterns knot library.

Install with::

    pip install pirn-agents

The agents domain has no heavy core dependencies — concrete LLM, memory,
and tool providers are user-supplied through interfaces defined in this
domain. Importing this package self-registers every ``Knot`` subclass in
the tree with the shared registry via
``sweet_tea.registry.Registry.fill_registry()`` so the knots become
resolvable by name through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory`.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

import warnings

from sweet_tea.registry import Registry
from sweet_tea.sweet_tea_warning import SweetTeaWarning

from pirn_agents.capability_probe import available_extras
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.tool import Tool
from pirn_agents.tool_decorator import FunctionTool, tool
from pirn_agents.tools.bundles import (
    calculator_toolset,
    data_toolset,
    filesystem_toolset,
    retrieval_toolset,
    sandbox_toolset,
    web_toolset,
)
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.tools.filesystem.glob_tool import GlobTool
from pirn_agents.tools.filesystem.list_dir_tool import ListDirTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.filesystem.write_file_tool import WriteFileTool
from pirn_agents.tools.retrieval.rag_tool import RagTool
from pirn_agents.tools.retrieval.retriever_tool import RetrieverTool
from pirn_agents.tools.sandbox.python_exec_tool import PythonExecTool
from pirn_agents.tools.sandbox.sandbox_backend import SandboxBackend
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor
from pirn_agents.tools.sandbox.sandbox_result import SandboxResult
from pirn_agents.tools.sandbox.shell_tool import ShellTool
from pirn_agents.tools.sandbox.subprocess_sandbox_backend import SubprocessSandboxBackend
from pirn_agents.tools.sql.aiosqlite_connector import AiosqliteConnector
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.sql.sqlite_connector import SqliteConnector
from pirn_agents.tools.web.html_to_text_tool import HtmlToTextTool
from pirn_agents.tools.web.http_request_tool import HttpRequestTool
from pirn_agents.tools.web.search_backend import SearchBackend
from pirn_agents.tools.web.web_search_tool import WebSearchTool
from pirn_agents.toolset import Toolset

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SweetTeaWarning)
    Registry.fill_registry(module=__name__, library="pirn")

__all__ = [
    "AiosqliteConnector",
    "CalculatorTool",
    "FunctionTool",
    "GlobTool",
    "HtmlToTextTool",
    "HttpRequestTool",
    "ListDirTool",
    "McpTool",
    "PythonExecTool",
    "RagTool",
    "ReadFileTool",
    "RetrieverTool",
    "SandboxBackend",
    "SandboxExecutor",
    "SandboxResult",
    "SearchBackend",
    "ShellTool",
    "SqlConnector",
    "SqlQueryTool",
    "SqliteConnector",
    "SubprocessSandboxBackend",
    "Tool",
    "Toolset",
    "WebSearchTool",
    "WriteFileTool",
    "available_extras",
    "calculator_toolset",
    "data_toolset",
    "filesystem_toolset",
    "retrieval_toolset",
    "sandbox_toolset",
    "tool",
    "web_toolset",
]
