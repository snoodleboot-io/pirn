"""``AgentToolCall`` — one call of an agent-as-tool, run as a nested pipeline.

A ``SubTapestry`` agent is already a ``Knot``, so exposing it as a tool needs
no adapter for *execution*: one call is one instance of the agent class,
built from the arguments the model supplied plus whatever the tool bound
(ADR agents-speaks-core, WS1).  What the call still needs is the policy an
agent-as-tool carries that a bare knot does not, and this container applies
it around the nested run:

* **nesting** — the inner tapestry gets a ``max_nesting_depth`` derived from
  the call's resolved ``max_depth`` (agent-as-tool frames, two nested runs
  each; a literal or an upstream knot's output alike), so
  core's :class:`~pirn.core.run_nesting.RunNesting` guard refuses runaway
  recursion and an agent re-entering itself (``NestedRunCycleError``), and
  the container's nesting key is the *agent* class, not this wrapper;
* **budget** — the ambient :class:`~pirn_agents.agent.agent_tool_policy.AgentToolPolicy`
  meter is inherited (or built from the tool's ``budget``), spent one
  iteration per call before the run and the response's tokens after it;
* **provider** — a pooled ``LLMProvider`` is threaded into the agent's ``llm``
  input when it declares one, so nested agents reuse it by identity.

Algorithm:
    1. ``__call__`` — merge the literal inputs with the resolved parent
       values, resolve the inherited policy, build this call's policy with
       the effective meter/provider (the call's own ``budget``/``provider``,
       wired or literal), spend an iteration, bind it, and run the knot;
       afterwards spend the response's tokens.
    2. ``process()`` — open an inner tapestry capped at
       ``RunNesting.current().depth + 2 * max_depth``, construct
       ``agent_class(**bound, **arguments, llm=provider?,
       _config=KnotConfig(id=tool_name))`` in it, run it through
       ``NestedRunKnot._run_inner`` and return the agent's output (an
       ``AgentResponse``), or its ``Skipped``.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Mapping
from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.run_nesting import RunNesting
from pirn.core.skipped import Skipped
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.agent.agent_response_mapper import AgentResponseMapper
from pirn_agents.agent.agent_tool_policy import AgentToolPolicy
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.types.messaging.agent_response import AgentResponse


class AgentToolCall(NestedRunKnot):
    """Run one agent-as-tool call under nesting, budget and provider policy."""

    def __init__(
        self,
        *,
        arguments: Knot | Mapping[str, Any],
        agent_class: Any,
        tool_name: Knot | str,
        agent_id: Knot | str | None = None,
        bound: Knot | Mapping[str, Any] | None = None,
        budget: Any = None,
        provider: Any = None,
        max_depth: Knot | int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire one call.

        Args:
            arguments: The model's arguments for the agent's inputs.
            agent_class: The ``SubTapestry`` agent class to run (``Any``: a
                class has no pydantic schema for core's eager adapter build).
            tool_name: The declared tool name.
            agent_id: The knot id the agent instance runs under — the wrapped
                template's own id, so lineage names the agent as configured;
                defaults to ``tool_name``.
            bound: Inputs the tool bound at wrap time (the template agent's
                literal inputs).
            budget: A :class:`RunBudget` enforced when no ambient meter is
                active (``Any``: bound policy, never model-supplied).
            provider: A pooled ``LLMProvider`` to inject as ``llm``.
            max_depth: Agent-as-tool frames allowed below this call; each frame
                is two nested runs (this call and the agent), which
                ``process()`` turns into core's ``max_nesting_depth``.
            _config: Framework metadata; ``id`` is the call id.
        """
        super().__init__(
            arguments=arguments,
            agent_class=agent_class,
            tool_name=tool_name,
            agent_id=agent_id,
            bound=bound,
            budget=budget,
            provider=provider,
            max_depth=max_depth,
            _config=_config,
            **kwargs,
        )

    def _nesting_key(self) -> str:
        """The wrapped agent's key, so a cycle is *that agent* being called again below itself."""
        values = self.config_values
        agent_class = values.get("agent_class")
        agent_id = values.get("agent_id") or values.get("tool_name")
        if isinstance(agent_class, type):
            return f"{agent_class.__module__}.{agent_class.__qualname__}:{agent_id}:tool"
        return super()._nesting_key()

    async def __call__(self, parent_results: Mapping[str, Any]) -> Result[Any]:
        """Bind the budget/provider context around the nested run and account for it.

        The policy inputs are read from the literal inputs merged with the
        resolved parent values, so a ``budget`` or ``provider`` wired from an
        upstream knot applies exactly like a literal one.
        """
        values: dict[str, Any] = {**self.config_values, **parent_results}
        base = AgentToolPolicy.current()
        meter: RunBudgetMeter | None = base.meter
        budget = values.get("budget")
        if meter is None and isinstance(budget, RunBudget):
            meter = RunBudgetMeter(budget)
        own_provider = values.get("provider")
        provider = own_provider if own_provider is not None else base.provider
        policy = AgentToolPolicy(meter=meter, provider=provider)
        if meter is not None:
            meter.token.raise_if_cancelled()
            meter.checkpoint()
            meter.spend_iteration()
        start = time.perf_counter()
        with AgentToolPolicy.bind(policy):
            result = await super().__call__(parent_results)
        if not isinstance(result, Skipped):
            await AgentCallRecorder.record(
                knot_id=self.knot_id,
                kind="tool",
                ok=isinstance(result, Ok),
                latency=time.perf_counter() - start,
                detail=result.record.message if isinstance(result, Err) else None,
                tool_name=values.get("tool_name"),
                call_id=self.knot_id,
                agent_id=values.get("agent_id"),
            )
        if meter is not None and isinstance(result, Ok) and isinstance(result.value, AgentResponse):
            tokens = AgentResponseMapper().summarise_tokens(result.value.metadata.usage)
            if tokens is not None:
                meter.spend_tokens(tokens)
        return result

    async def process(
        self,
        arguments: Mapping[str, Any],
        agent_class: Any,
        tool_name: str,
        agent_id: str | None = None,
        bound: Mapping[str, Any] | None = None,
        budget: Any = None,
        provider: Any = None,
        max_depth: int = 8,
        **_: Any,
    ) -> Any:
        """Run the agent for this call as a nested run capped at ``max_depth`` frames.

        Args:
            arguments: The model's arguments.
            agent_class: The agent class to instantiate.
            tool_name: The declared tool name.
            agent_id: The agent knot's id; defaults to ``tool_name``.
            bound: Inputs bound at wrap time; ``arguments`` override them.
            budget: Applied by ``__call__`` around this run; declared so the
                input is visible to lineage.
            provider: The pooled provider to inject as ``llm`` when the agent
                declares that input and the call did not supply one.
            max_depth: Agent-as-tool frames allowed below this call.

        Returns:
            The agent's output, or the agent's ``Skipped`` when its run skipped it.

        Raises:
            TypeError: If ``agent_class`` is not a ``SubTapestry`` class or
                ``max_depth`` is not an int.
            ValueError: If ``max_depth`` is not positive.
        """
        if not (isinstance(agent_class, type) and issubclass(agent_class, SubTapestry)):
            raise TypeError(
                f"AgentToolCall: agent_class must be a SubTapestry class, got {agent_class!r}"
            )
        if isinstance(max_depth, bool) or not isinstance(max_depth, int):
            raise TypeError(f"AgentToolCall: max_depth must be an int, got {max_depth!r}")
        if max_depth <= 0:
            raise ValueError(f"AgentToolCall: max_depth must be positive, got {max_depth}")
        inputs: dict[str, Any] = {**(bound or {}), **arguments}
        effective = provider if provider is not None else AgentToolPolicy.current().provider
        if effective is not None and "llm" not in arguments and self._accepts(agent_class, "llm"):
            inputs["llm"] = effective
        knot_id = ToolFactory.knot_id_for(agent_id if agent_id else tool_name)
        with Tapestry(max_nesting_depth=RunNesting.current().depth + 2 * max_depth) as inner:
            agent_class(**inputs, _config=KnotConfig(id=knot_id))
        run = await self._run_inner(inner)
        if knot_id in run.skipped:
            reason = next(
                (
                    row.skip_reason
                    for row in run.lineage
                    if row.knot_id == knot_id and row.skip_reason
                ),
                "skipped",
            )
            return Skipped(reason=reason)
        return run.outputs[knot_id]

    @staticmethod
    def _accepts(agent_class: type[Knot], name: str) -> bool:
        """Whether the agent's ``process`` declares a parameter ``name``."""
        try:
            return name in inspect.signature(agent_class.process).parameters
        except (TypeError, ValueError):
            return False
