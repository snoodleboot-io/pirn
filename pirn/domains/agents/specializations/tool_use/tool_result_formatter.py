"""``ToolResultFormatter`` — format a :class:`ToolResult` for LLM injection.

Converts a :class:`ToolResult` into a human-readable string suitable for
injection as a message into the next LLM chat turn.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.tool_result import ToolResult


class ToolResultFormatter(Knot):
    """Format a ToolResult as a human-readable string for the next LLM message."""

    def __init__(
        self,
        *,
        tool_result: Knot | ToolResult,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tool_result=tool_result, _config=_config, **kwargs)

    async def process(
        self,
        tool_result: ToolResult,
        **_: Any,
    ) -> str:
        """Format the ToolResult as a readable string for LLM message injection.

        Args:
            tool_result: The ToolResult to format.

        Returns:
            A human-readable string representation of the tool result.

        Raises:
            TypeError: If tool_result is not a ToolResult.
        """
        if not isinstance(tool_result, ToolResult):
            raise TypeError(
                "ToolResultFormatter: tool_result must be a ToolResult, "
                f"got {type(tool_result).__name__}"
            )
        if tool_result.error is not None:
            return (
                f"Tool call '{tool_result.call_id}' failed with error: "
                f"{tool_result.error}"
            )
        result_repr = self._format_result(tool_result.result)
        return f"Tool call '{tool_result.call_id}' returned: {result_repr}"

    @staticmethod
    def _format_result(result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list)):
            import json
            try:
                return json.dumps(result, indent=2)
            except (TypeError, ValueError):
                return str(result)
        return str(result)
