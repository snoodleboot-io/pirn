"""Characterization of the WS5/S1 (PIR-698) domain-subpackage import surface.

S1 is a behavior-preserving refactor that ``git mv``\\s flat root modules of
``pirn_agents`` into domain subpackages (``agent``, ``tools``, ``llm``,
``connectors``, ``embeddings``, ``memory``, ``security``, ``_internal``). This
test pins the *post-move* public import surface: every symbol listed below must
be importable at its NEW module path, so the move is proven to preserve the
public API.

Imports are performed with :func:`importlib.import_module` inside the test body
(not at module top) so this file always COLLECTS cleanly even before the moves
land -- only the assertions fail until the refactor completes.
"""

from __future__ import annotations

import importlib

import pytest

# (new_module_path, public_symbol_name) rows that the S1 move must satisfy.
# Every public (non-underscore) class/function each moved module defines is
# characterized here -- including the extra context accessors, the async
# authorization helper, and the decorator functions -- plus the two
# intentionally-underscored modules and the one symbol that stays at root.
_S1_IMPORT_SURFACE: list[tuple[str, str]] = [
    # agent domain subpackage
    ("pirn_agents.agent.agent_invoker", "AgentInvoker"),
    ("pirn_agents.agent.agent_introspector", "AgentIntrospector"),
    ("pirn_agents.agent.agent_schema_deriver", "AgentSchemaDeriver"),
    ("pirn_agents.agent.agent_response_mapper", "AgentResponseMapper"),
    ("pirn_agents.agent.agent_tool_context", "AgentToolContext"),
    ("pirn_agents.agent.agent_tool_context", "current_agent_tool_context"),
    ("pirn_agents.agent.agent_tool_context", "bind_agent_tool_context"),
    ("pirn_agents.agent.async_fanout_engine", "AsyncFanoutEngine"),
    ("pirn_agents.agent.parallel_tool_executor", "ParallelToolExecutor"),
    ("pirn_agents.agent.approval_hook", "ApprovalHook"),
    ("pirn_agents.agent.approval_hook", "authorize_tool_call"),
    # tools domain subpackage
    ("pirn_agents.tools.tool", "Tool"),
    ("pirn_agents.tools.tool_registry", "ToolRegistry"),
    ("pirn_agents.tools.toolset", "Toolset"),
    ("pirn_agents.tools.function_tool", "FunctionTool"),
    ("pirn_agents.tools.agent_tool", "AgentTool"),
    ("pirn_agents.tools.as_tool", "as_tool"),
    ("pirn_agents.tools.agent_as_tool_mixin", "AgentAsToolMixin"),
    ("pirn_agents.tools.tool_decorator", "tool"),
    ("pirn_agents.tools.tool_call_codec", "ToolCallCodec"),
    ("pirn_agents.tools.tool_permissions", "ToolPermissions"),
    ("pirn_agents.tools.tool_invocation_hook", "ToolInvocationHook"),
    ("pirn_agents.tools.tool_schema_compiler", "ToolSchemaCompiler"),
    ("pirn_agents.tools.streaming_tool_call_parser", "StreamingToolCallParser"),
    # llm domain subpackage
    ("pirn_agents.llm.llm_provider", "LLMProvider"),
    ("pirn_agents.llm.provider_adapter", "ProviderAdapter"),
    # connectors domain subpackage
    ("pirn_agents.connectors.connector_lifespan", "connector_lifespan"),
    # embeddings domain subpackage
    ("pirn_agents.embeddings.embedding_provider", "EmbeddingProvider"),
    # memory domain subpackage
    ("pirn_agents.memory.memory_store", "MemoryStore"),
    # security domain subpackage (intentionally underscored module)
    ("pirn_agents.security._safe_pattern_compiler", "SafePatternCompiler"),
    # internal helper subpackage (intentionally underscored module + symbol)
    ("pirn_agents._internal._require", "_require"),
    # NOT moved: remains importable at the package root.
    ("pirn_agents.capability_probe", "CapabilityProbe"),
]


@pytest.mark.parametrize(
    ("module_path", "symbol_name"),
    _S1_IMPORT_SURFACE,
    ids=[f"{module}:{symbol}" for module, symbol in _S1_IMPORT_SURFACE],
)
def test_symbol_importable_at_new_path(module_path: str, symbol_name: str) -> None:
    module = importlib.import_module(module_path)
    symbol = getattr(module, symbol_name)
    assert symbol is not None
