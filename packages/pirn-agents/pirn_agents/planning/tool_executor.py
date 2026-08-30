"""``ToolExecutor`` — invoke a single :class:`ToolCall` against the matching tool.

Algorithm:
    1. Receive the resolved ``ToolCall`` and ``tools`` sequence.
    2. Validate input types at process time.
    3. Build a registry mapping tool names to tool instances.
    4. Look up the tool by ``call.tool_name``; if not found, return an error ``ToolResult``.
    5. Invoke ``tool.invoke(call.arguments)``; catch any exception and surface as an error result.
    6. Return a successful ``ToolResult`` with the invocation result.


References:
    - :class:`pirn_agents.tools.tool.Tool`
    - :class:`pirn_agents.tools.tool_call.ToolCall`
    - :class:`pirn_agents.tools.tool_result.ToolResult`
    - :class:`pirn.connectors.dsn_scrubber.DsnScrubber`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult


@knot
async def _unknown_tool(call: ToolCall) -> ToolResult:
    """Terminal for a call naming a tool that is not registered.

    A knot rather than an early return because ``process`` now returns the sink
    of an inner pipeline: both branches have to be nodes so both are recorded.
    """
    return ToolResult(
        call_id=call.call_id,
        result=None,
        error=f"unknown tool {call.tool_name!r}",
    )


class ToolExecutor(SubTapestry):
    """Executes a :class:`ToolCall` against the matching :class:`Tool`.

    The dispatch decision — which registered tool does this call name — stays
    here; the invocation itself is delegated to a
    :class:`~pirn_agents.tools.tool_invocation.ToolInvocation` returned as the
    inner pipeline's sink, so the call runs *through the engine* and gets its
    own ``Result`` and ``KnotLineage`` row instead of being awaited inline
    (PIR-733).

    That is why this is a :class:`~pirn.nodes.sub_tapestry.SubTapestry` rather
    than a plain ``Knot``: a knot awaited from inside another knot's
    ``process`` bypasses the engine, which is the very thing this ticket exists
    to stop. Returning the sink is the sanctioned way to build a node whose body
    is itself a graph.

    Exceptions raised by :meth:`Tool.invoke` are still surfaced as a
    :class:`ToolResult` with an ``error`` rather than propagating — that
    contract is unchanged, and credential scrubbing now happens inside
    ``ToolInvocation`` so the batch and single-call paths cannot drift apart
    again.
    """

    def __init__(
        self,
        *,
        call: Knot,
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            call=call,
            tools=tools,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        call: ToolCall,
        tools: Sequence[Tool],
        **_: Any,
    ) -> Knot:
        """Resolve ``call`` to a tool and return the invocation knot that runs it.

        Args:
            call: The tool call specifying the tool name, arguments, and call ID.
            tools: The registered tools available for dispatch.

        Returns:
            The sink of the inner pipeline: a
            :class:`~pirn_agents.tools.tool_invocation.ToolInvocation` for a
            matched tool, or an ``unknown-tool`` terminal otherwise. Its output —
            a :class:`ToolResult` — becomes this knot's output, so the value
            callers see is unchanged.

        Raises:
            TypeError: If call is not a ToolCall or tools contains non-Tool elements.
            ValueError: If tools is empty.
        """
        if not isinstance(call, ToolCall):
            raise TypeError(f"ToolExecutor: call must be a ToolCall, got {type(call).__name__}")
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            raise TypeError("ToolExecutor: tools must be a sequence of Tool instances")
        if not tools:
            raise ValueError("ToolExecutor: tools must be non-empty")
        for index, tool in enumerate(tools):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolExecutor: tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
        registry = {tool.name: tool for tool in tools}
        tool = registry.get(call.tool_name)
        if tool is None:
            return _unknown_tool(call=call, _config=KnotConfig(id="unknown-tool"))
        return ToolInvocation(tool=tool, call=call, _config=KnotConfig(id="invoke"))
