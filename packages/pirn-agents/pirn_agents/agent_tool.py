"""``AgentTool`` — expose any ``SubTapestry`` agent anywhere a ``Tool`` is accepted.

Wrapping an agent in :class:`AgentTool` turns "agent-as-tool" from a
hand-written adapter (see PATTERNS.md Pattern 16) into a one-liner. ``name`` and
``description`` default from the agent but are overridable; ``parameters_schema``
is derived from the agent's declared inputs (falling back to ``{task: str}``);
and :meth:`invoke` runs the inner agent and maps its :class:`AgentResponse` into
the F1 :class:`~pirn_agents.types.tool_result.ToolResult` shape.

All safety and performance behaviour — recursion/cycle guards, inherited
budgets, and pooled-provider reuse — lives in the shared
:func:`~pirn_agents.agent_invocation.invoke_agent` machinery, so a tool-style
call and a handoff/swarm transfer behave identically.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.agent_invocation import invoke_agent
from pirn_agents.agent_schema import derive_agent_schema
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.tool import Tool
from pirn_agents.types.tool_result import ToolResult


def _default_name(agent: SubTapestry) -> str:
    """Derive a snake_case tool name from the agent's class name."""
    class_name = type(agent).__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()


def _default_description(agent: SubTapestry, name: str) -> str:
    """Derive a description from the agent's class docstring, or a generic line."""
    doc = (type(agent).__doc__ or "").strip()
    if doc:
        return doc.split("\n\n")[0].strip()
    return f"Run the {name} agent as a tool."


class AgentTool(Tool):
    """A :class:`Tool` that runs a wrapped :class:`SubTapestry` agent."""

    def __init__(
        self,
        agent: SubTapestry,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: Mapping[str, Any] | None = None,
        provider: LLMProvider | None = None,
        budget: RunBudget | None = None,
        max_depth: int = 8,
    ) -> None:
        """Wrap ``agent`` as a tool.

        Args:
            agent: The ``SubTapestry`` agent to expose.
            name: Tool name; defaults to the agent's snake_case class name.
            description: Tool description; defaults to the agent's docstring.
            input_schema: Explicit JSON-Schema ``parameters`` object; derived
                from the agent's ``process`` signature when omitted.
            provider: A pooled provider nested agents should reuse.
            budget: A budget enforced across this tool's (possibly nested) run.
            max_depth: Maximum agent-as-tool nesting depth.

        Raises:
            TypeError: If ``agent`` is not a ``SubTapestry`` or ``max_depth`` is
                not a positive int.
        """
        if not isinstance(agent, SubTapestry):
            raise TypeError(f"AgentTool: agent must be a SubTapestry, got {type(agent).__name__}")
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth <= 0:
            raise TypeError(f"AgentTool: max_depth must be a positive int, got {max_depth!r}")
        self._agent = agent
        self._name = name if name is not None else _default_name(agent)
        self._description = (
            description if description is not None else _default_description(agent, self._name)
        )
        self._schema: dict[str, Any] = (
            dict(input_schema) if input_schema is not None else dict(derive_agent_schema(agent))
        )
        self._provider = provider
        self._budget = budget
        self._max_depth = max_depth

    @property
    def agent(self) -> SubTapestry:
        """The wrapped agent."""
        return self._agent

    @property
    def name(self) -> str:
        """Tool identifier the planner uses to address the agent."""
        return self._name

    @property
    def description(self) -> str:
        """Human-readable description shown to the planner."""
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """JSON Schema describing the agent's task inputs."""
        return self._schema

    async def invoke(self, arguments: Mapping[str, Any]) -> ToolResult:
        """Run the wrapped agent and return its F1 :class:`ToolResult`.

        Delegates to the shared :func:`~pirn_agents.agent_invocation.invoke_agent`
        machinery so recursion guards, budget inheritance, and provider reuse
        apply uniformly. An inner-agent failure surfaces as a tool error result
        rather than an unhandled exception.
        """
        return await invoke_agent(
            self._agent,
            arguments,
            name=self._name,
            schema=self._schema,
            provider=self._provider,
            budget=self._budget,
            max_depth=self._max_depth,
        )

    def _clear_credentials(self) -> None:
        """Drop the pooled provider reference held for nested reuse."""
        self._provider = None

    def __repr__(self) -> str:
        return f"<AgentTool name={self._name!r} agent={type(self._agent).__name__}>"
