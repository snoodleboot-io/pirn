"""``FallbackChain`` — invoke ordered candidates until one succeeds.

Algorithm:
    1. Receive the ``ordered`` candidates (confidence-descending), the tool
       ``arguments``, and the ``confidences`` mapping.
    2. Validate types at process time.
    3. Walk the candidates in order:
       - Skip any whose confidence is below its ``min_confidence`` floor
         (a deterministic low-confidence fallback trigger).
       - Otherwise invoke its tool; on success return immediately; on a raised
         exception or non-OK result, fall through to the next candidate.
    4. Return a typed :class:`FallbackResult` recording the outcome, the
       candidates attempted, and the candidates skipped.

By stopping at the first success and skipping sub-threshold candidates the chain
avoids the wasted invocations a naive "retry every candidate" baseline pays.

References:
    - Anthropic (2024) "Building effective agents" — routing + fallback
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing.fallback_result import FallbackResult
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class FallbackChain(Knot):
    """Try confidence-ordered candidates until one returns a successful result."""

    def __init__(
        self,
        *,
        ordered: Knot | Sequence[RouteCandidate],
        arguments: Knot | Mapping[str, Any],
        confidences: Knot | Mapping[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ordered=ordered,
            arguments=arguments,
            confidences=confidences,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        ordered: Sequence[RouteCandidate],
        arguments: Mapping[str, Any],
        confidences: Mapping[str, float],
        **_: Any,
    ) -> FallbackResult:
        """Dispatch through the ordered candidates and return a typed result.

        Args:
            ordered: Candidates in confidence-descending order.
            arguments: Arguments passed to each invoked tool.
            confidences: Confidence per candidate name (missing = 0.0).

        Returns:
            A :class:`FallbackResult` describing the outcome.

        Raises:
            TypeError: If ``ordered`` holds a non-:class:`RouteCandidate` or
                ``arguments``/``confidences`` are not mappings.
        """
        candidate_tuple = tuple(ordered)
        for index, candidate in enumerate(candidate_tuple):
            if not isinstance(candidate, RouteCandidate):
                raise TypeError(
                    f"FallbackChain: ordered[{index}] must be a RouteCandidate, got "
                    f"{type(candidate).__name__}"
                )
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"FallbackChain: arguments must be a Mapping, got {type(arguments).__name__}"
            )
        if not isinstance(confidences, Mapping):
            raise TypeError(
                f"FallbackChain: confidences must be a Mapping, got {type(confidences).__name__}"
            )

        attempted: list[str] = []
        skipped: list[str] = []
        for candidate in candidate_tuple:
            if confidences.get(candidate.name, 0.0) < candidate.min_confidence:
                skipped.append(candidate.name)
                continue
            attempted.append(candidate.name)
            result = await self._invoke(candidate, arguments)
            if result.status is ToolStatus.OK:
                return FallbackResult(
                    succeeded=True,
                    chosen=candidate.name,
                    result=result,
                    attempted=tuple(attempted),
                    skipped=tuple(skipped),
                )
        return FallbackResult(
            succeeded=False,
            chosen=None,
            result=None,
            attempted=tuple(attempted),
            skipped=tuple(skipped),
        )

    @staticmethod
    async def _invoke(candidate: RouteCandidate, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            value = await candidate.tool.invoke(arguments)
        except Exception as exc:
            return ToolResult(call_id=candidate.name, result=None, error=str(exc))
        return ToolResult(call_id=candidate.name, result=value, status=ToolStatus.OK)
