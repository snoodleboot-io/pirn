"""``invoke_agent`` — the single machinery that runs a nested agent as a tool.

Every agent-as-tool call — whether dispatched as a plain
:class:`~pirn_agents.agent_tool.AgentTool` or as a handoff/swarm transfer —
funnels through :func:`invoke_agent` so the guarantees never diverge:

* **Recursion + cycle guard** (F7-S3): a child
  :class:`~pirn_agents.agent_tool_context.AgentToolContext` is entered before
  the nested agent runs, raising before over-deep or self-referential recursion.
* **Budget propagation** (F7-S4): the parent's shared
  :class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` is inherited
  (never re-created) and spent per nested call, so a nested loop cannot outrun
  the caller's deadline/token/iteration limits.
* **Shared provider reuse** (F7-S5): the parent's pooled
  :class:`~pirn.core.providers.llm_provider.LLMProvider` is threaded into the
  nested run rather than reconstructed on the hot path.
* **Result mapping** (F7-S1): the inner :class:`AgentResponse` is mapped to the
  F1 :class:`ToolResult` shape; an inner failure surfaces as a tool error, not
  an unhandled exception.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Mapping
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.agent_response_mapper import (
    agent_response_to_tool_result,
    summarise_tokens,
)
from pirn_agents.agent_tool_context import (
    AgentToolContext,
    bind_agent_tool_context,
    current_agent_tool_context,
)
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


def _agent_key(agent: object) -> str:
    """Return a stable per-agent identity used for cycle detection."""
    knot_id = getattr(agent, "knot_id", None)
    if isinstance(knot_id, str) and knot_id:
        return knot_id
    return f"{type(agent).__name__}:{id(agent)}"


def _accepts_parameter(agent: object, name: str) -> bool:
    """Return whether the agent's ``process`` declares a parameter ``name``."""
    process = getattr(type(agent), "process", None)
    if process is None:
        return False
    try:
        signature = inspect.signature(process)
    except (TypeError, ValueError):
        return False
    return name in signature.parameters


def _primary_parameter(schema: Mapping[str, Any]) -> str | None:
    """Return the primary task parameter name from a derived schema."""
    required = schema.get("required")
    if isinstance(required, (list, tuple)) and required:
        return str(required[0])
    properties = schema.get("properties")
    if isinstance(properties, Mapping) and properties:
        return str(next(iter(properties)))
    return None


def _resolve_call_id(arguments: Mapping[str, Any], name: str) -> str:
    """Pick the tool-call id from ``arguments`` or fall back to a stable token."""
    call_id = arguments.get("call_id")
    if isinstance(call_id, str) and call_id:
        return call_id
    return f"{name}-call"


def _map_arguments(
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
    primary = _primary_parameter(schema)
    if primary is not None and primary not in mapped:
        for alias in ("input", "task", "query"):
            if alias in mapped:
                mapped[primary] = mapped[alias]
                break
    if provider is not None and _accepts_parameter(agent, "llm"):
        mapped.setdefault("llm", provider)
    return mapped


async def invoke_agent(
    agent: object,
    arguments: Mapping[str, Any],
    *,
    name: str,
    schema: Mapping[str, Any],
    provider: LLMProvider | None = None,
    budget: RunBudget | None = None,
    max_depth: int = 8,
) -> ToolResult:
    """Run ``agent`` as a nested tool and return an F1 :class:`ToolResult`.

    Args:
        agent: The ``SubTapestry`` agent to run to completion.
        arguments: Tool arguments; aliased and forwarded as the agent's inputs.
        name: Tool name, used to derive a fallback call id.
        schema: The tool's parameters schema, used to locate the primary input.
        provider: An explicit pooled provider to reuse; inherits the ambient
            context's provider when ``None``.
        budget: A budget to enforce when no ambient meter is active; ignored
            once a parent meter is being inherited.
        max_depth: Maximum nesting depth for a *root* invocation; nested calls
            inherit the root's cap.

    Returns:
        A :class:`ToolResult` wrapping the structured :class:`AgentResponse`, or
        an error result when the inner agent fails.

    Raises:
        AgentDepthExceededError: If entering the agent exceeds the depth cap.
        AgentCycleError: If the agent is already active on the call stack.
        BudgetBreachError: If the inherited budget is exhausted.
    """
    parent = current_agent_tool_context()
    base = parent if parent is not None else AgentToolContext(max_depth=max_depth)

    meter: RunBudgetMeter | None = base.meter
    if meter is None and budget is not None:
        meter = RunBudgetMeter(budget)
    effective_provider = provider if provider is not None else base.provider

    child = base.child(_agent_key(agent), meter=meter, provider=effective_provider)

    if meter is not None:
        meter.token.raise_if_cancelled()
        meter.checkpoint()
        meter.spend_iteration()

    parent_results = _map_arguments(agent, arguments, schema, effective_provider)
    call_id = _resolve_call_id(arguments, name)

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
        tokens = summarise_tokens(response.usage)
        if tokens is not None:
            meter.spend_tokens(tokens)
    return agent_response_to_tool_result(response, call_id=call_id, latency=latency)
