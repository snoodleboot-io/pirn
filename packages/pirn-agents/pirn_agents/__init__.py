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

from pirn_agents.agent_as_tool_mixin import AgentAsToolMixin
from pirn_agents.agent_tool import AgentTool
from pirn_agents.approval_hook import ApprovalHook, authorize_tool_call
from pirn_agents.as_tool import as_tool
from pirn_agents.blob_store_knot import BlobStoreKnot
from pirn_agents.builder.agent import Agent
from pirn_agents.builder.agent_builder import AgentBuilder
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.agent_presets import AgentPresets
from pirn_agents.builder.agent_spec import AgentSpec
from pirn_agents.builder.agent_spec_loader import AgentSpecLoader
from pirn_agents.capability_probe import available_extras
from pirn_agents.connector_lifespan import connector_lifespan
from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.connectors.http_search_connector import HttpSearchConnector
from pirn_agents.connectors.local_blob_store import LocalBlobStore
from pirn_agents.connectors.s3_blob_store import S3BlobStore
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.function_tool import FunctionTool
from pirn_agents.graph_rag.entity_relation_extractor import EntityRelationExtractor
from pirn_agents.graph_rag.extracted_entity import ExtractedEntity
from pirn_agents.graph_rag.extracted_relation import ExtractedRelation
from pirn_agents.graph_rag.extraction_result import ExtractionResult
from pirn_agents.graph_rag.extraction_schema import ExtractionSchema
from pirn_agents.graph_rag.graph_context_builder import GraphContextBuilder
from pirn_agents.graph_rag.graph_embedding_index import GraphEmbeddingIndex
from pirn_agents.graph_rag.graph_traversal import GraphTraversal
from pirn_agents.graph_rag.hybrid_graph_retriever import HybridGraphRetriever
from pirn_agents.graph_rag.node_embedding_index import NodeEmbeddingIndex
from pirn_agents.graph_rag.subgraph import Subgraph
from pirn_agents.graph_rag.traversal_budget import TraversalBudget
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_neighbor import GraphNeighbor
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore
from pirn_agents.http_connector_knot import HttpConnectorKnot
from pirn_agents.mcp.mcp_tool import McpTool
from pirn_agents.search_connector_knot import SearchConnectorKnot
from pirn_agents.sql_connector_knot import SqlConnectorKnot
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.testing.tool_test_harness import ToolTestHarness, make_stub_tool
from pirn_agents.tool import Tool
from pirn_agents.tool_decorator import tool
from pirn_agents.tool_permissions import ToolPermissions
from pirn_agents.tool_registry import ToolRegistry
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
    "Agent",
    "AgentAsToolMixin",
    "AgentBuilder",
    "AgentPatternRegistry",
    "AgentPresets",
    "AgentSpec",
    "AgentSpecLoader",
    "AgentTool",
    "AiosqliteConnector",
    "ApprovalHook",
    "BlobStore",
    "BlobStoreKnot",
    "CalculatorTool",
    "EntityRelationExtractor",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionResult",
    "ExtractionSchema",
    "FunctionTool",
    "GlobTool",
    "GraphContextBuilder",
    "GraphEdge",
    "GraphEmbeddingIndex",
    "GraphNeighbor",
    "GraphNode",
    "GraphStore",
    "GraphTraversal",
    "HtmlToTextTool",
    "HttpConnector",
    "HttpConnectorKnot",
    "HttpRequestTool",
    "HttpSearchConnector",
    "HybridGraphRetriever",
    "InMemoryGraphStore",
    "ListDirTool",
    "LocalBlobStore",
    "McpTool",
    "NodeEmbeddingIndex",
    "PythonExecTool",
    "RagTool",
    "ReadFileTool",
    "RetrieverTool",
    "S3BlobStore",
    "SandboxBackend",
    "SandboxExecutor",
    "SandboxResult",
    "SearchBackend",
    "SearchConnectorKnot",
    "ShellTool",
    "SqlConnector",
    "SqlConnectorKnot",
    "SqlQueryTool",
    "SqlServiceConnector",
    "SqliteConnector",
    "StubTool",
    "Subgraph",
    "SubprocessSandboxBackend",
    "Tool",
    "ToolPermissions",
    "ToolRegistry",
    "ToolTestHarness",
    "Toolset",
    "TraversalBudget",
    "WebSearchTool",
    "WriteFileTool",
    "as_tool",
    "authorize_tool_call",
    "available_extras",
    "calculator_toolset",
    "connector_lifespan",
    "data_toolset",
    "filesystem_toolset",
    "make_stub_tool",
    "retrieval_toolset",
    "sandbox_toolset",
    "tool",
    "web_toolset",
]
