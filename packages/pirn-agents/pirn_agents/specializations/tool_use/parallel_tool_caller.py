"""``ParallelToolCaller`` — invoke multiple tools concurrently, through the engine.

Takes a list of :class:`ToolCall` instances and a sequence of tool
capabilities and returns the collected :class:`ToolResult` list, one per
call, in input order.

A thin, retry-free, timeout-free specialisation of
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`'s job:
where that class tunes concurrency, per-call timeouts and retries for a
batch workload, this one exists for the common case — call everything, wait
for it all, and report each outcome. What *is* shared is the unit of work:
every call is a tool knot, ``factory.for_call(call)`` (ADR agents-speaks-core,
WS1), so a tool call gets lineage/history/``Ok|Err|Skipped`` regardless of
which execution site dispatched it.

Algorithm:
    1. Receive the resolved ``tool_calls`` and ``tools`` (each validated into
       a :class:`ToolFactory`).
    2. Build a name-keyed registry from ``tools``.
    3. For each call, look up the tool by name: a match becomes a tool knot
       under the call's id; a miss, or arguments the declaration refuses,
       becomes a :class:`~pirn_agents.tools.tool_call_rejection.ToolCallRejection`
       recorded as that call's own ``Err``.
    4. Wire every per-call knot as a parent of one
       :class:`~pirn.nodes.aggregator.Aggregator` with
       ``error_policy=RECEIVE_ERRORS``, so the *engine* schedules the fan-out
       concurrently and the combine sees each call's raw ``Result``.
    5. Return the aggregator (or, for zero calls, a ``Parameter`` defaulting
       to ``[]`` — an ``Aggregator`` requires at least one parent) as the
       inner pipeline's sink; its output — the :class:`ToolResult` views in
       input order — becomes this knot's output.

References:
    - :class:`pirn_agents.tools.tool_factory.ToolFactory`
    - :class:`pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`
    - :class:`pirn_agents.planning.tool_executor.ToolExecutor`
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class ParallelToolCaller(AgentPipeline):
    """Call multiple tools in parallel, through the engine, and collect their results."""

    # Every call's ``Err`` is delivered to the Aggregator, not to this knot.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        tool_calls: Knot | Sequence[ToolCall],
        tools: Knot | Sequence[Any],
        approval_hook: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            tool_calls=tool_calls,
            tools=tools,
            approval_hook=approval_hook,
            _config=_config,
            **kwargs,
        )

    def _make_inner_tapestry(self) -> Tapestry:
        """A tapestry whose fallback ``traceback_filter`` redacts secrets."""
        return Tapestry(traceback_filter=SecretRedactor.default_traceback_filter())

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        tools: Sequence[ToolFactory],
        approval_hook: Any = None,
        **_: Any,
    ) -> Knot:
        """Resolve every call to a capability and return the fan-out knot that runs them.

        Args:
            tool_calls: The sequence of ToolCall instances to execute concurrently.
            tools: The capabilities available for invocation.
            approval_hook: The approval hook to consult for a call whose tool
                requires approval (PIR-865); see
                :meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call`.

        Returns:
            The sink of the inner pipeline: an :class:`~pirn.nodes.aggregator.Aggregator`
            over one tool knot (or rejection) per call, whose output — a
            ``list[ToolResult]`` in input order — becomes this knot's output.

        Raises:
            TypeError: If any element of ``tools`` is not a tool capability, or
                any element of ``tool_calls`` is not a :class:`ToolCall`.
        """
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            try:
                ToolFactory.of(tool)
            except TypeError as exc:
                raise TypeError(
                    f"ParallelToolCaller: tools[{index}] must be a Tool, got {type(tool).__name__}"
                ) from exc
        registry: dict[str, ToolFactory] = {}
        for tool in tool_list:
            factory = ToolFactory.of(tool)
            registry[factory.name] = factory

        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolCaller: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )

        if not call_list:
            return Parameter("empty", list, default=[], _config=KnotConfig(id="empty"))

        per_call: dict[str, Knot] = {}
        used_ids: set[str] = set()
        for index, call in enumerate(call_list):
            knot_id = ToolFactory.knot_id_for(call.call_id)
            if knot_id in used_ids:
                knot_id = f"{knot_id}-{index}"
            used_ids.add(knot_id)
            per_call[f"call_{index}"] = self._call_knot(
                call, registry.get(call.tool_name), knot_id, approval_hook
            )

        return Aggregator(
            combine=functools.partial(self._collect_in_order, call_list),
            _config=KnotConfig(id="agg", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            **per_call,
        )

    @staticmethod
    def _call_knot(
        call: ToolCall,
        factory: ToolFactory | None,
        knot_id: str,
        approval_hook: Any = None,
    ) -> Knot:
        """The knot that runs ``call``: the tool knot, or a rejection recorded as its ``Err``."""
        if factory is None:
            return ToolCallRejection(
                call=call,
                error=ToolNotFoundError(call.tool_name, call.call_id),
                _config=KnotConfig(id=knot_id),
            )
        try:
            return factory.for_call(call, knot_id=knot_id, approval_hook=approval_hook)
        except ToolArgumentValidationError as exc:
            return ToolCallRejection(call=call, error=exc, _config=KnotConfig(id=knot_id))

    @staticmethod
    def _collect_in_order(calls: Sequence[ToolCall], **by_key: Result[Any]) -> list[ToolResult]:
        """Build the ``call_{index}``-keyed fan-out outcomes into views, in input order."""
        return [
            ToolResult.from_result(call.call_id, by_key[f"call_{index}"])
            for index, call in enumerate(calls)
        ]
