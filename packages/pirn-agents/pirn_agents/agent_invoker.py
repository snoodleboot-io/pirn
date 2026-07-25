"""``AgentInvoker`` — the single machinery that runs a nested agent as a tool.

Every agent-as-tool call — whether dispatched as a plain
:class:`~pirn_agents.agent_tool.AgentTool` or as a handoff/swarm transfer —
funnels through :meth:`AgentInvoker.invoke` so the guarantees never diverge:

* **Recursion + cycle guard** (F7-S3): a child
  :class:`~pirn_agents.agent_tool_context.AgentToolContext` is entered before
  the nested agent runs, raising before over-deep or self-referential recursion.
* **Budget propagation** (F7-S4): the parent's shared
  :class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` is inherited
  (never re-created) and spent per nested call, so a nested loop cannot outrun
  the caller's deadline/token/iteration limits.
* **Shared provider reuse** (F7-S5): the parent's pooled
  :class:`~pirn_agents.llm_provider.LLMProvider` is threaded into the
  nested run rather than reconstructed on the hot path.
* **Result mapping** (F7-S1): the inner :class:`AgentResponse` is mapped to the
  F1 :class:`ToolResult` shape; an inner failure surfaces as a tool error, not
  an unhandled exception.

The invoker is constructed with the caller's ``max_depth`` / ``budget`` /
``provider`` and reused per nested call. Agent reflection (``getattr`` /
:mod:`inspect`) is delegated to an :class:`AgentIntrospector` collaborator so the
dynamic dispatch lives in one typed place.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from pirn_agents.agent_introspector import AgentIntrospector
from pirn_agents.agent_response_mapper import AgentResponseMapper
from pirn_agents.agent_tool_context import (
    AgentToolContext,
    bind_agent_tool_context,
    current_agent_tool_context,
)
from pirn_agents.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class AgentInvoker:
    """Runs a nested agent as a tool with recursion/budget/provider guarantees."""

    def __init__(
        self,
        *,
        max_depth: int = 8,
        budget: RunBudget | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        """Bind the invoker to the caller's nested-run configuration.

        Args:
            max_depth: Maximum nesting depth for a *root* invocation; nested
                calls inherit the root's cap.
            budget: A budget to enforce when no ambient meter is active; ignored
                once a parent meter is being inherited.
            provider: An explicit pooled provider to reuse; inherits the ambient
                context's provider when ``None``.
        """
        self._max_depth: int = max_depth
        self._budget: RunBudget | None = budget
        self._provider: LLMProvider | None = provider
        self._introspector: AgentIntrospector = AgentIntrospector()
        self._response_mapper = AgentResponseMapper()

    async def invoke(
        self,
        agent: object,
        arguments: Mapping[str, Any],
        *,
        name: str,
        schema: Mapping[str, Any],
    ) -> ToolResult:
        """Run ``agent`` as a nested tool and return an F1 :class:`ToolResult`.

        Args:
            agent: The ``SubTapestry`` agent to run to completion.
            arguments: Tool arguments; aliased and forwarded as the agent's inputs.
            name: Tool name, used to derive a fallback call id.
            schema: The tool's parameters schema, used to locate the primary input.

        Returns:
            A :class:`ToolResult` wrapping the structured :class:`AgentResponse`,
            or an error result when the inner agent fails.

        Raises:
            AgentDepthExceededError: If entering the agent exceeds the depth cap.
            AgentCycleError: If the agent is already active on the call stack.
            BudgetBreachError: If the inherited budget is exhausted.
        """
        parent = current_agent_tool_context()
        base = parent if parent is not None else AgentToolContext(max_depth=self._max_depth)

        meter: RunBudgetMeter | None = base.meter
        if meter is None and self._budget is not None:
            meter = RunBudgetMeter(self._budget)
        effective_provider = self._provider if self._provider is not None else base.provider

        child = base.child(
            self._introspector.agent_key(agent), meter=meter, provider=effective_provider
        )

        if meter is not None:
            meter.token.raise_if_cancelled()
            meter.checkpoint()
            meter.spend_iteration()

        parent_results = self._map_arguments(agent, arguments, schema, effective_provider)
        call_id = self._resolve_call_id(arguments, name)

        start = time.perf_counter()
        with bind_agent_tool_context(child):
            result = await agent(parent_results)  # type: ignore[operator]
        latency = time.perf_counter() - start

        if result.is_err:
            record = result.record
            return ToolResult(
                call_id=call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=f"{record.exc_type}: {record.message}",
                latency=latency,
            )

        value = result.value
        response = value if isinstance(value, AgentResponse) else AgentResponse(content=str(value))
        if meter is not None:
            tokens = self._response_mapper.summarise_tokens(response.usage)
            if tokens is not None:
                meter.spend_tokens(tokens)
        return self._response_mapper.to_tool_result(response, call_id=call_id, latency=latency)

    def _map_arguments(
        self,
        agent: object,
        arguments: Mapping[str, Any],
        schema: Mapping[str, Any],
        provider: LLMProvider | None,
    ) -> dict[str, Any]:
        """Translate incoming tool ``arguments`` into the agent's ``process`` inputs.

        The nested run receives the arguments as parent results that override the
        agent's construction-time constants. A lone ReAct-style ``input`` (or
        ``task``/``query``) argument is aliased onto the agent's primary parameter
        so a wrapped agent works unchanged inside a stock ReAct loop. When a pooled
        ``provider`` is being propagated and the agent accepts an ``llm`` parameter,
        it is injected so the nested agent reuses the parent's provider by identity.
        """
        mapped = {key: value for key, value in arguments.items() if key != "call_id"}
        primary = self._primary_parameter(schema)
        if primary is not None and primary not in mapped:
            for alias in ("input", "task", "query"):
                if alias in mapped:
                    mapped[primary] = mapped[alias]
                    break
        if provider is not None and self._introspector.accepts_parameter(agent, "llm"):
            mapped.setdefault("llm", provider)
        return mapped

    @staticmethod
    def _primary_parameter(schema: Mapping[str, Any]) -> str | None:
        """Return the primary task parameter name from a derived schema."""
        required = schema.get("required")
        if isinstance(required, (list, tuple)) and required:
            return str(required[0])
        properties = schema.get("properties")
        if isinstance(properties, Mapping) and properties:
            return str(next(iter(properties)))
        return None

    @staticmethod
    def _resolve_call_id(arguments: Mapping[str, Any], name: str) -> str:
        """Pick the tool-call id from ``arguments`` or fall back to a stable token."""
        call_id = arguments.get("call_id")
        if isinstance(call_id, str) and call_id:
            return call_id
        return f"{name}-call"
