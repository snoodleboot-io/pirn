"""``ToolResultAggregator`` — merge a sequence of :class:`ToolResult`s into a mapping.

Algorithm:
    1. Receive the resolved sequence of ``ToolResult`` instances.
    2. Validate input types at process time.
    3. For each result, map ``call_id → result`` if successful, or ``call_id → {"error": msg}`` if not.
    4. Return the aggregated dict.


References:
    - :class:`pirn.domains.agents.types.tool_result.ToolResult`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.tool_result import ToolResult


class ToolResultAggregator(Knot):
    """Reduces a sequence of :class:`ToolResult` to a context-friendly dict.

    Successful results become ``{call_id: result}`` entries; failed
    results become ``{call_id: {"error": <message>}}`` so downstream
    knots see a uniform mapping shape they can splice into the agent
    context.
    """

    def __init__(
        self,
        *,
        results: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(results=results, _config=_config, **kwargs)

    async def process(
        self,
        results: Sequence[ToolResult],
        **_: Any,
    ) -> dict[str, Any]:
        """Reduce a sequence of ToolResults into a call_id-keyed mapping of results or errors.

        Args:
            results: The sequence of tool results to aggregate.

        Returns:
            A dict mapping each call_id to its result value or an error dict.

        Raises:
            TypeError: If results is not a sequence or any element is not a ToolResult.
        """
        if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
            raise TypeError(
                "ToolResultAggregator: results must be a sequence of "
                f"ToolResult, got {type(results).__name__}"
            )
        aggregated: dict[str, Any] = {}
        for index, result in enumerate(results):
            if not isinstance(result, ToolResult):
                raise TypeError(
                    f"ToolResultAggregator: results[{index}] must be a "
                    f"ToolResult, got {type(result).__name__}"
                )
            if result.error is None:
                aggregated[result.call_id] = result.result
            else:
                aggregated[result.call_id] = {"error": result.error}
        return aggregated
