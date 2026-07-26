"""Characterization of the WS5/S6 (PIR-703) taxonomy import surface.

S6 is a behavior-preserving refactor that relocates flat ``pirn_agents.types``
modules (and a couple of neighbors) into taxonomy subpackages: ``content`` and
``messaging`` under ``types``, the tool value objects under ``tools``, the plan
under ``planning``, and the RAG relevance check under its canonical name. This
test pins the *post-move* public import surface -- every symbol below must be
importable at its NEW module path, so the move is proven to preserve the public
API -- and asserts that each OLD module path is GONE (guarding against a
regression that would leave a stale shim behind).

Imports are performed with :func:`importlib.import_module` inside the test body
(not at module top) so this file always COLLECTS cleanly even before the moves
land -- only the assertions fail until the refactor completes.
"""

from __future__ import annotations

import importlib

import pytest

# (new_module_path, public_symbol_name) rows that the S6 move must satisfy.
_S6_IMPORT_SURFACE: list[tuple[str, str]] = [
    # content taxonomy subpackage
    ("pirn_agents.types.content.content_block", "ContentBlock"),
    ("pirn_agents.types.content.text_block", "TextBlock"),
    ("pirn_agents.types.content.image_block", "ImageBlock"),
    ("pirn_agents.types.content.audio_block", "AudioBlock"),
    ("pirn_agents.types.content.file_block", "FileBlock"),
    ("pirn_agents.types.content.media_handle", "MediaHandle"),
    ("pirn_agents.types.content.message_content", "MessageContent"),
    ("pirn_agents.types.content.tool_result_block", "ToolResultBlock"),
    # messaging taxonomy subpackage
    ("pirn_agents.types.messaging.agent_message", "AgentMessage"),
    ("pirn_agents.types.messaging.agent_context", "AgentContext"),
    ("pirn_agents.types.messaging.agent_response", "AgentResponse"),
    # tools value objects
    ("pirn_agents.tools.tool_call", "ToolCall"),
    ("pirn_agents.tools.tool_result", "ToolResult"),
    ("pirn_agents.tools.tool_status", "ToolStatus"),
    # planning
    ("pirn_agents.planning.plan", "Plan"),
    # specializations
    ("pirn_agents.specializations.rag.relevance_check", "RelevanceCheck"),
    ("pirn_agents.specializations.multi_agent._response_echo", "_ResponseEcho"),
]

# OLD flat module paths that the S6 move must remove entirely.
_S6_REMOVED_MODULES: list[str] = [
    "pirn_agents.types.tool_call",
    "pirn_agents.types.tool_result",
    "pirn_agents.types.tool_status",
    "pirn_agents.types.plan",
    "pirn_agents.types.content_block",
    "pirn_agents.types.agent_response",
    "pirn_agents.types.agent_message",
    "pirn_agents.specializations.rag.relevance_gate",
]


@pytest.mark.parametrize(
    ("module_path", "symbol_name"),
    _S6_IMPORT_SURFACE,
    ids=[f"{module}:{symbol}" for module, symbol in _S6_IMPORT_SURFACE],
)
def test_symbol_importable_at_new_path(module_path: str, symbol_name: str) -> None:
    module = importlib.import_module(module_path)
    symbol = getattr(module, symbol_name)
    assert symbol is not None
    assert callable(symbol), f"{module_path}:{symbol_name} is not a class/callable"


@pytest.mark.parametrize("module_path", _S6_REMOVED_MODULES, ids=_S6_REMOVED_MODULES)
def test_old_module_path_is_gone(module_path: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_path)
