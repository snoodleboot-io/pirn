"""``as_tool`` — free-function helper wrapping a ``SubTapestry`` as an ``AgentTool``.

This is the functional form of the agent-as-tool API. The
:class:`~pirn_agents.tools.agent_as_tool_mixin.AgentAsToolMixin` delegates its
``agent.as_tool(...)`` method here so both spellings share one implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tools.agent_tool import AgentTool


class AsTool:
    """Namespace for the functional agent-as-tool wrapper."""

    @staticmethod
    def wrap(
        agent: SubTapestry,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        provider: LLMProvider | None = None,
        budget: RunBudget | None = None,
        max_depth: int = 8,
    ) -> AgentTool:
        """Wrap ``agent`` as an :class:`AgentTool` with no hand-written adapter.

        Args:
            agent: The ``SubTapestry`` agent to expose as a tool.
            name: Override tool name; defaults from the agent.
            description: Override tool description; defaults from the agent.
            input_schema: Explicit parameters schema; derived from the agent when
                omitted.
            provider: A pooled provider nested agents should reuse.
            budget: A budget enforced across the (possibly nested) run.
            max_depth: Maximum agent-as-tool nesting depth (8 by default);
                enforced by core's ``RunNesting`` guard.

        Returns:
            An :class:`AgentTool` ready to drop into any ``Tool`` slot.
        """
        return AgentTool(
            agent,
            name=name,
            description=description,
            input_schema=input_schema,
            provider=provider,
            budget=budget,
            max_depth=max_depth,
        )


def as_tool(
    agent: SubTapestry,
    *,
    name: str | None = None,
    description: str | None = None,
    input_schema: Mapping[str, Any] | None = None,
    provider: LLMProvider | None = None,
    budget: RunBudget | None = None,
    max_depth: int = 8,
) -> AgentTool:
    """Wrap ``agent`` as an :class:`AgentTool` with no hand-written adapter.

    Thin wrapper kept for the pinned public import path (see
    ``tests/test_ws5_s1_import_surface.py``) and the
    :meth:`~pirn_agents.tools.agent_as_tool_mixin.AgentAsToolMixin.as_tool`
    delegation; see :meth:`AsTool.wrap`.
    """
    return AsTool.wrap(
        agent,
        name=name,
        description=description,
        input_schema=input_schema,
        provider=provider,
        budget=budget,
        max_depth=max_depth,
    )
