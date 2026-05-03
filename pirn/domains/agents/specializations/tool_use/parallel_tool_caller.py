"""``ParallelToolCaller`` — invoke multiple tools concurrently.

Takes a list of :class:`ToolCall` instances and a registry of :class:`Tool`
objects, calls each tool in parallel via ``asyncio.gather``, and returns
the collected :class:`ToolResult` list.
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
        tools: Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ParallelToolCaller: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        self._tool_registry: dict[str, Tool] = {
            tool.name: tool for tool in tool_list
        }
        super().__init__(tool_calls=tool_calls, _config=_config, **kwargs)

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        **_: Any,
    ) -> list[ToolResult]:
        """Invoke all tool calls in parallel and return the collected results.

        Args:
            tool_calls: The sequence of ToolCall instances to execute concurrently.

        Returns:
            A list of ToolResult instances in the same order as the input calls.

        Raises:
            TypeError: If any element of tool_calls is not a ToolCall.
        """
        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolCaller: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )

        async def _invoke(call: ToolCall) -> ToolResult:
            tool = self._tool_registry.get(call.tool_name)
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
