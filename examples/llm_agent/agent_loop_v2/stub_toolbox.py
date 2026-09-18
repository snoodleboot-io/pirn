"""``StubToolbox`` — the one set of offline doubles every inner pipeline shares.

Part of the ``examples.llm_agent.agent_loop_v2`` example.  The providers and the
three bound tool capabilities are built once here, so the three ``SubTapestry``
runners wire the same objects instead of each minting its own — and nothing has
to live at module scope to be shared.
"""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.tools.tool_factory import ToolFactory

from examples.llm_agent.agent_loop_v2.planner_scripted_llm_provider import (
    PlannerScriptedLLMProvider,
)
from examples.llm_agent.agent_loop_v2.scripted_llm_provider import ScriptedLLMProvider
from examples.llm_agent.agent_loop_v2.stub_tool import StubTool


class StubToolbox:
    """The shared stub LLM providers and tool capabilities."""

    llm: ClassVar[ScriptedLLMProvider] = ScriptedLLMProvider(seed=42)
    planner_llm: ClassVar[PlannerScriptedLLMProvider] = PlannerScriptedLLMProvider(seed=0)

    search_tool: ClassVar[ToolFactory] = StubTool.bind(
        result_template="Search result for '{arg}': found 3 relevant documents "
        "covering historical context, current status, and future outlook.",
    ).named("search", description="Search for information on a topic.")
    calculate_tool: ClassVar[ToolFactory] = StubTool.bind(
        result_template="calculate({arg}) = 6125.00"
    ).named("calculate", description="Evaluate a mathematical expression.")
    lookup_tool: ClassVar[ToolFactory] = StubTool.bind(
        result_template="lookup('{arg}'): policy states standard 30-day processing "
        "window; exceptions require manager approval.",
    ).named("lookup", description="Look up a fact in the knowledge base.")

    all_tools: ClassVar[tuple[ToolFactory, ...]] = (search_tool, calculate_tool, lookup_tool)
