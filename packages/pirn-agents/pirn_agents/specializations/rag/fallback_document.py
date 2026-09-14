"""``FallbackDocument`` — wrap a fallback tool's result into the doc shape."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.tool_result import ToolResult


class FallbackDocument(Knot):
    """Wrap the fallback tool's result into the single-doc list shape."""

    def __init__(
        self,
        *,
        tool_result: Knot | ToolResult,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tool_result=tool_result, _config=_config, **kwargs)

    async def process(self, tool_result: ToolResult, **_: Any) -> list[Mapping[str, Any]]:
        """Return ``[{"source": "fallback", "content": str(result)}]``.

        Args:
            tool_result: The fallback tool's invocation outcome.

        Returns:
            A single-entry document list wrapping the tool's result.

        Raises:
            RuntimeError: If the fallback tool call itself failed.
        """
        if not tool_result.succeeded:
            raise RuntimeError(f"CorrectiveRouter: fallback_tool call failed: {tool_result.error}")
        return [{"source": "fallback", "content": str(tool_result.result)}]
