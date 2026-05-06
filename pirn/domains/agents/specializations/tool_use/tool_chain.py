"""``ToolChain`` — execute a fixed sequence of tools, piping output to input.

Takes an initial :class:`ToolCall` and a sequence of :class:`Tool` instances.
Executes the first call, feeds its result as ``input`` to the next tool in
the chain, and so on. Returns the final :class:`ToolResult`.

Algorithm:
    1. Receive resolved ``initial_call`` and ``tools`` at process time.
    2. Validate that ``tools`` is non-empty and each entry is a :class:`Tool`.
    3. Validate that ``initial_call`` is a :class:`ToolCall`.
    4. Seed ``current_arguments`` from ``initial_call.arguments``.
    5. For each tool in sequence: invoke with current arguments, wrap in
       :class:`ToolResult`, update ``current_arguments`` to ``{"input": raw}``.
    6. On any exception, return a :class:`ToolResult` with the error string.
    7. Return the final :class:`ToolResult`.


References:
    - pirn-native design; no external references.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.domains.agents.types.tool_result import ToolResult


class ToolChain(Knot):
    """Execute a sequence of tools, passing each output as input to the next."""

    def __init__(
        self,
        *,
        initial_call: Knot | ToolCall,
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(initial_call=initial_call, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        initial_call: ToolCall,
        tools: Sequence[Tool],
        **_: Any,
    ) -> ToolResult:
        """Execute the tool chain, feeding each output as input to the next tool.

        Args:
            initial_call: The first ToolCall to execute, which seeds the chain.
            tools: The ordered sequence of Tool instances to execute.

        Returns:
            The final ToolResult after running all tools in sequence.

        Raises:
            TypeError: If initial_call is not a ToolCall or any entry in tools is not a Tool.
            ValueError: If tools is empty.
        """
        tool_list = list(tools)
        if not tool_list:
            raise ValueError("ToolChain: tools must not be empty")
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolChain: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        if not isinstance(initial_call, ToolCall):
            raise TypeError(
                "ToolChain: initial_call must be a ToolCall, "
                f"got {type(initial_call).__name__}"
            )
        current_arguments: dict[str, Any] = dict(initial_call.arguments)
        current_call_id = initial_call.call_id
        last_result: ToolResult | None = None

        for tool in tool_list:
            try:
                raw = await tool.invoke(current_arguments)
                last_result = ToolResult(call_id=current_call_id, result=raw)
                current_arguments = {"input": raw}
            except Exception as exc:
                return ToolResult(
                    call_id=current_call_id,
                    result=None,
                    error=str(exc),
                )

        if last_result is None:
            return ToolResult(
                call_id=initial_call.call_id,
                result=None,
                error="ToolChain: no tools executed",
            )
        return last_result
