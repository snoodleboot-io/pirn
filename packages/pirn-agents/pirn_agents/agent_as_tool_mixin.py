"""``AgentAsToolMixin`` — adds ``.as_tool()`` to a ``SubTapestry`` agent.

Mix this into a ``SubTapestry`` subclass to expose the ergonomic
``agent.as_tool(...)`` API. The method simply delegates to the
:func:`~pirn_agents.as_tool.as_tool` free function, so the mixin adds no state
and stays compatible with the agent's existing construction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.as_tool import as_tool
from pirn_agents.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget

if TYPE_CHECKING:
    from pirn_agents.agent_tool import AgentTool


class AgentAsToolMixin:
    """Provides an ``as_tool()`` method returning an :class:`AgentTool`."""

    def as_tool(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        provider: LLMProvider | None = None,
        budget: RunBudget | None = None,
        max_depth: int = 8,
    ) -> AgentTool:
        """Return an :class:`AgentTool` wrapping this agent.

        See :func:`~pirn_agents.as_tool.as_tool` for the argument semantics.
        """
        return as_tool(
            cast(SubTapestry, self),
            name=name,
            description=description,
            input_schema=input_schema,
            provider=provider,
            budget=budget,
            max_depth=max_depth,
        )
