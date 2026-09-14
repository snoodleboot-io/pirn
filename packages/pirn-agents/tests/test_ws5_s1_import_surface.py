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
# Every public class each moved module defines is characterized here (the
# former module-level accessors/decorators are static methods on these classes,
# PIR-872) -- plus the intentionally-underscored module and the one symbol that
# stays at root.
_S1_IMPORT_SURFACE: list[tuple[str, str]] = [
    # agent domain subpackage
    ("pirn_agents.agent.agent_introspector", "AgentIntrospector"),
    ("pirn_agents.agent.agent_response_mapper", "AgentResponseMapper"),
    ("pirn_agents.agent.agent_tool_policy", "AgentToolPolicy"),
    ("pirn_agents.agent.parallel_tool_executor", "ParallelToolExecutor"),
    ("pirn_agents.agent.approval_hook", "ApprovalHook"),
    # tools domain subpackage
    ("pirn_agents.tools.tool", "Tool"),
    ("pirn_agents.tools.tool_registry", "ToolRegistry"),
    ("pirn_agents.tools.toolset", "Toolset"),
    ("pirn_agents.tools.function_tool", "FunctionTool"),
    ("pirn_agents.tools.agent_tool", "AgentTool"),
    ("pirn_agents.tools.as_tool", "AsTool"),
    ("pirn_agents.tools.agent_as_tool_mixin", "AgentAsToolMixin"),
    ("pirn_agents.tools.tool_decorator", "ToolDecorator"),
    ("pirn_agents.tools.tool_call_codec", "ToolCallCodec"),
    ("pirn_agents.tools.tool_permissions", "ToolPermissions"),
    ("pirn_agents.tools.streaming_tool_call_parser", "StreamingToolCallParser"),
    # llm domain subpackage
    ("pirn_agents.llm.llm_provider", "LLMProvider"),
    ("pirn_agents.llm.provider_adapter", "ProviderAdapter"),
    # connectors domain subpackage
    ("pirn_agents.connectors.connector_lifespan", "ConnectorLifespan"),
    # embeddings domain subpackage
    ("pirn_agents.retrieval.embeddings.embedding_provider", "EmbeddingProvider"),
    # memory domain subpackage
    ("pirn_agents.memory.stores.memory_store", "MemoryStore"),
    # security domain subpackage (intentionally underscored module)
    ("pirn_agents.security._safe_pattern_compiler", "SafePatternCompiler"),
    # internal helper subpackage
    ("pirn_agents._internal.json_shape", "JsonShape"),
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
