"""``ParallelToolCaller`` — invoke multiple tools concurrently.

Takes a list of :class:`ToolCall` instances and a registry of :class:`Tool`
objects, calls each tool in parallel via ``asyncio.gather``, and returns
the collected :class:`ToolResult` list.

Algorithm:
    1. Validate that each element of ``tool_calls`` is a :class:`ToolCall`.
    2. Build a name-keyed registry from the supplied ``tools`` sequence.
    3. For each call, look up the tool by name; emit a not-found error result
       if the name is absent from the registry.
    4. Invoke all tools concurrently via ``asyncio.gather``; catch exceptions
       per-call and convert them to error results.
    5. Return the results list in the same order as the input calls.


References:
    - Python ``asyncio.gather`` documentation:
      https://docs.python.org/3/library/asyncio-task.html#asyncio.gather
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult


class ParallelToolCaller(Knot):
    """Call multiple tools in parallel and collect their results."""

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
    ) -> list[ToolResult]:
        """Invoke all tool calls in parallel and return the collected results.

        Args:
            tool_calls: The sequence of ToolCall instances to execute concurrently.
            tools: The sequence of Tool instances available for invocation.

        Returns:
            A list of ToolResult instances in the same order as the input calls.

        Raises:
            TypeError: If any element of tools is not a Tool or tool_calls element
                is not a ToolCall.
        """
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ParallelToolCaller: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        tool_registry: dict[str, Tool] = {tool.name: tool for tool in tool_list}

        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolCaller: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )

        async def _invoke(call: ToolCall) -> ToolResult:
            tool = tool_registry.get(call.tool_name)
            if tool is None:
                return ToolResult(
                    call_id=call.call_id,
                    result=None,
                    error=f"Tool '{call.tool_name}' not found",
                )
            try:
                result = await tool.invoke(call.arguments)
                return ToolResult(call_id=call.call_id, result=result)
            except Exception as exc:
                return ToolResult(
                    call_id=call.call_id,
                    result=None,
                    error=str(exc),
                )

        return list(await asyncio.gather(*(_invoke(c) for c in call_list)))
