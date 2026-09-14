"""``ToolResultFormatter`` — format a :class:`ToolResult` for LLM injection.

Converts a :class:`ToolResult` into a human-readable string suitable for
injection as a message into the next LLM chat turn.

Algorithm:
    1. Receive the resolved ``tool_result`` at process time.
    2. Validate that ``tool_result`` is a :class:`ToolResult`.
    3. If ``tool_result.error`` is set, return a failure message string.
    4. Otherwise, format ``tool_result.result`` via ``_format_result``.
    5. Return the formatted string prefixed with the call ID.


References:
    - pirn-native design; no external references.
"""

from __future__ import annotations

import json
from typing import Any, TypeGuard

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.tool_result import ToolResult


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
        """
        if tool_result.error is not None:
            return f"Tool call '{tool_result.call_id}' failed with error: {tool_result.error}"
        result_repr = self._format_result(tool_result.result)
        return f"Tool call '{tool_result.call_id}' returned: {result_repr}"

    @staticmethod
    def _format_result(result: object) -> str:
        if isinstance(result, str):
            return result
        if ToolResultFormatter._is_json_container(result):
            try:
                return json.dumps(result, indent=2)
            except (TypeError, ValueError):
                return str(result)
        return str(result)

    @staticmethod
    def _is_json_container(value: object) -> TypeGuard[dict[str, object] | list[object]]:
        """Narrow a tool result to the shapes rendered as indented JSON."""
        return isinstance(value, (dict, list))
