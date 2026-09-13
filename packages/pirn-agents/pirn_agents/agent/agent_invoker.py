"""``AgentInvoker`` — deprecated (one cycle); an agent-as-tool call is a knot now.

Before the ADR "agents speaks core" (WS1) every agent-as-tool call funnelled
through this class: it bound a private nesting context, enforced its own
depth/cycle guard, propagated the budget meter and pooled provider, awaited
the agent directly, and mapped the response to a ``ToolResult``.  Each of
those now lives where core puts it — the depth/cycle guard is core's
``RunNesting`` applied by :class:`~pirn_agents.tools.agent_tool_call.AgentToolCall`
to the nested run, budget/provider ride
:class:`~pirn_agents.agent.agent_tool_context.AgentToolContext` around it,
and the call runs as a knot with its own ``Result`` — so :meth:`invoke`
forwards to :class:`~pirn_agents.tools.agent_tool.AgentTool` and warns.  The
class will be removed next cycle.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.agent.agent_nesting_config import AgentNestingConfig
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tools.agent_tool import AgentTool
from pirn_agents.tools.tool_result import ToolResult


class AgentInvoker:
    """Deprecated shim over :class:`AgentTool`."""

    def __init__(
        self,
        *,
        max_depth: int = AgentNestingConfig.max_depth,
        budget: RunBudget | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        """Bind the invoker to the caller's nested-run configuration (see :class:`AgentTool`)."""
        warnings.warn(
            "AgentInvoker is deprecated (ADR agents-speaks-core WS1): wrap the agent with "
            "AgentTool and run the call as a knot",
            DeprecationWarning,
            stacklevel=2,
        )
        self._max_depth: int = max_depth
        self._budget: RunBudget | None = budget
        self._provider: LLMProvider | None = provider

    async def invoke(
        self,
        agent: object,
        arguments: Mapping[str, Any],
        *,
        name: str,
        schema: Mapping[str, Any],
    ) -> ToolResult:
        """Run ``agent`` as a nested tool and return the ``ToolResult`` view.

        Raises:
            TypeError: If ``agent`` is not a ``SubTapestry``.
            BudgetBreachError: If the inherited budget is exhausted before the
                run starts.
        """
        if not isinstance(agent, SubTapestry):
            raise TypeError(
                f"AgentInvoker: agent must be a SubTapestry, got {type(agent).__name__}"
            )
        tool = AgentTool(
            agent,
            name=name,
            input_schema=schema,
            provider=self._provider,
            budget=self._budget,
            max_depth=self._max_depth,
        )
        return await tool.run_view(arguments)
