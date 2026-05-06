"""``ToolExecutor`` — invoke a single :class:`ToolCall` against the matching tool.

Algorithm:
    1. Receive the resolved ``ToolCall`` and ``tools`` sequence.
    2. Validate input types at process time.
    3. Build a registry mapping tool names to tool instances.
    4. Look up the tool by ``call.tool_name``; if not found, return an error ``ToolResult``.
    5. Invoke ``tool.invoke(call.arguments)``; catch any exception and surface as an error result.
    6. Return a successful ``ToolResult`` with the invocation result.


References:
    - :class:`pirn.domains.agents.tool.Tool`
    - :class:`pirn.domains.agents.types.tool_call.ToolCall`
    - :class:`pirn.domains.agents.types.tool_result.ToolResult`
    - :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class ToolExecutor(Knot):
    """Executes a :class:`ToolCall` against the matching :class:`Tool`.

    Exceptions raised by :meth:`Tool.invoke` are caught and surfaced
    as a :class:`ToolResult` whose ``error`` field is the stringified
    exception, leaving the caller free to decide how to react.
    """

    _scrubber: ClassVar[DsnScrubber] = DsnScrubber()

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
    ) -> ToolResult:
        """Dispatch a ToolCall to the matching tool and return the result or a captured error.

        Args:
            call: The tool call specifying the tool name, arguments, and call ID.
            tools: The registered tools available for dispatch.

        Returns:
            A ToolResult with the invocation result or a stringified error if invocation failed.

        Raises:
            TypeError: If call is not a ToolCall or tools contains non-Tool elements.
            ValueError: If tools is empty.
        """
        if not isinstance(call, ToolCall):
            raise TypeError(
                "ToolExecutor: call must be a ToolCall, "
                f"got {type(call).__name__}"
            )
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            raise TypeError(
                "ToolExecutor: tools must be a sequence of Tool instances"
            )
        if not tools:
            raise ValueError("ToolExecutor: tools must be non-empty")
        for index, tool in enumerate(tools):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolExecutor: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        registry = {tool.name: tool for tool in tools}
        tool = registry.get(call.tool_name)
        if tool is None:
            return ToolResult(
                call_id=call.call_id,
                result=None,
                error=f"unknown tool {call.tool_name!r}",
            )
        try:
            value = await tool.invoke(call.arguments)
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                result=None,
                error=f"{type(exc).__name__}: {type(self)._scrubber.scrub(str(exc))}",
            )
        return ToolResult(call_id=call.call_id, result=value, error=None)
