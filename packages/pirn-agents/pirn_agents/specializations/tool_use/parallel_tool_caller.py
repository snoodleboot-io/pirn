"""``ParallelToolCaller`` — invoke multiple tools concurrently, through the engine.

Takes a list of :class:`ToolCall` instances and a registry of :class:`Tool`
objects and returns the collected :class:`ToolResult` list, one per call, in
input order.

A thin, retry-free, timeout-free specialisation of
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`'s job:
where that class tunes concurrency, per-call timeouts, retries, and hooks for
a batch workload, this one exists for the common case — call everything, wait
for it all, and report each outcome. It does not subclass
``ParallelToolExecutor`` because their inputs differ in kind rather than in
degree: this class takes a plain ``Sequence[Tool]`` (no
:class:`~pirn_agents.tools.toolset.Toolset` to build), and has no
retry/timeout/hook surface to inherit — every one of those parameters would be
dead weight on this constructor. What *is* shared is the invocation unit
itself: every per-call dispatch here is a
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation`, the same knot
``ParallelToolExecutor`` and :class:`~pirn_agents.planning.tool_executor.ToolExecutor`
use, so a tool call gets lineage/history/``Ok|Err|Skipped`` regardless of
which of the three call sites dispatched it (PIR-856).

Algorithm:
    1. Receive the resolved ``tool_calls`` and ``tools`` sequence.
    2. Validate every element's type.
    3. Build a name-keyed registry from ``tools``.
    4. For each call, look up the tool by name: a match becomes a
       :class:`ToolInvocation` parent; a miss becomes a small terminal knot
       carrying a not-found :class:`ToolResult` directly (mirroring
       :class:`~pirn_agents.planning.tool_executor.ToolExecutor`'s
       ``_unknown_tool``) — there is no tool to invoke, so there is nothing
       for ``ToolInvocation`` to do.
    5. Wire every per-call knot as a parent of one
       :class:`~pirn.nodes.aggregator.Aggregator`, so the *engine* schedules
       the fan-out concurrently (the same shape
       :class:`~pirn_agents.tools.tool_invocation.ToolInvocation`'s module
       docstring describes for PIR-714-style fan-out) instead of a
       hand-rolled ``asyncio.gather``.
    6. Return the aggregator (or, for zero calls, a trivial terminal
       returning ``[]`` — an ``Aggregator`` requires at least one parent) as
       the inner pipeline's sink; its output becomes this knot's output.

References:
    - :class:`pirn_agents.tools.tool_invocation.ToolInvocation`
    - :class:`pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`
    - :class:`pirn_agents.planning.tool_executor.ToolExecutor`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult


@knot
async def _tool_not_found(call: ToolCall) -> ToolResult:
    """Terminal for a call naming a tool absent from the registry.

    A knot rather than a plain error object built inline: every per-call
    outcome must be a graph node so it can sit as a parent of the fan-out
    ``Aggregator`` alongside the matched-tool ``ToolInvocation``s.
    """
    return ToolResult(
        call_id=call.call_id,
        result=None,
        error=f"Tool '{call.tool_name}' not found",
    )


@knot
async def _empty_results() -> list[ToolResult]:
    """Terminal for zero calls — an ``Aggregator`` requires at least one parent."""
    return []


class ParallelToolCaller(SubTapestry):
    """Call multiple tools in parallel, through the engine, and collect their results.

    The dispatch decision — which registered tool does each call name — stays
    here; every invocation itself is delegated to a ``ToolInvocation`` wired
    as a fan-out parent of one ``Aggregator`` returned as the inner pipeline's
    sink, so each call runs *through the engine* and gets its own ``Result``
    and ``KnotLineage`` row instead of being awaited inline under
    ``asyncio.gather`` (PIR-856, extending PIR-733's ``ToolExecutor`` pattern
    to the batch case).
    """

    def __init__(
        self,
        *,
        tool_calls: Knot | Sequence[ToolCall],
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tool_calls=tool_calls, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        tools: Sequence[Tool],
        **_: Any,
    ) -> Knot:
        """Resolve every call to a tool and return the fan-out knot that runs them.

        Args:
            tool_calls: The sequence of ToolCall instances to execute concurrently.
            tools: The sequence of Tool instances available for invocation.

        Returns:
            The sink of the inner pipeline: an :class:`~pirn.nodes.aggregator.Aggregator`
            over one :class:`ToolInvocation` (or not-found terminal) per call,
            whose output — a ``list[ToolResult]`` in input order — becomes
            this knot's output. A batch of zero calls returns a trivial
            terminal producing ``[]`` directly, since ``Aggregator`` requires
            at least one parent.

        Raises:
            TypeError: If any element of ``tools`` is not a :class:`Tool`, or
                any element of ``tool_calls`` is not a :class:`ToolCall`.
        """
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ParallelToolCaller: tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
        tool_registry: dict[str, Tool] = {tool.name: tool for tool in tool_list}

        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolCaller: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )

        if not call_list:
            return _empty_results(_config=KnotConfig(id="empty"))

        per_call: dict[str, Knot] = {}
        for index, call in enumerate(call_list):
            key = f"call_{index}"
            tool = tool_registry.get(call.tool_name)
            if tool is None:
                per_call[key] = _tool_not_found(
                    call=call, _config=KnotConfig(id=f"missing-{index}")
                )
            else:
                per_call[key] = ToolInvocation(
                    tool=tool, call=call, _config=KnotConfig(id=f"invoke-{index}")
                )

        return Aggregator(combine=self._collect_in_order, _config=KnotConfig(id="agg"), **per_call)

    @staticmethod
    def _collect_in_order(**by_key: ToolResult) -> list[ToolResult]:
        """Reassemble the ``call_{index}``-keyed fan-out results into input order."""
        ordered = sorted(by_key.items(), key=lambda item: int(item[0].split("_")[1]))
        return [result for _, result in ordered]
