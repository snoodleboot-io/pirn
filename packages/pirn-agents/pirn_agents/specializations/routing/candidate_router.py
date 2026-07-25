"""``CandidateRouter`` — order typed candidates best-first by confidence.

Algorithm:
    1. Receive ``candidates`` (Sequence[RouteCandidate]) and ``confidences``
       (Mapping name -> confidence, 0.0-1.0) at process time.
    2. Validate types at process time.
    3. Return the candidates sorted by confidence descending (a stable sort, so
       ties keep declaration order). The head is the primary route; the tail is
       the ordered fallback chain.

The confidence mapping is provider-neutral: it may come from an LLM intent
router, a heuristic, or a learned classifier — the router only orders on it.

References:
    - Anthropic (2024) "Building effective agents" — routing
    - :class:`pirn_agents.specializations.routing.confidence_router.ConfidenceRouter`
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing.route_candidate import RouteCandidate


class CandidateRouter(Knot):
    """Order typed :class:`RouteCandidate`s best-first by confidence."""

    def __init__(
        self,
        *,
        candidates: Knot | Sequence[RouteCandidate],
        confidences: Knot | Mapping[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            candidates=candidates,
            confidences=confidences,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        candidates: Sequence[RouteCandidate],
        confidences: Mapping[str, float],
        **_: Any,
    ) -> tuple[RouteCandidate, ...]:
        """Return the candidates ordered by confidence, highest first.

        Args:
            candidates: The typed candidates to order.
            confidences: Confidence per candidate name (missing = 0.0).

        Returns:
            A confidence-descending tuple of :class:`RouteCandidate`.

        Raises:
            TypeError: If ``candidates`` holds a non-:class:`RouteCandidate` or
                ``confidences`` is not a mapping.
        """
        candidate_tuple = tuple(candidates)
        for index, candidate in enumerate(candidate_tuple):
            if not isinstance(candidate, RouteCandidate):
                raise TypeError(
                    f"CandidateRouter: candidates[{index}] must be a RouteCandidate, got "
                    f"{type(candidate).__name__}"
                )
        if not isinstance(confidences, Mapping):
            raise TypeError(
                f"CandidateRouter: confidences must be a Mapping, got {type(confidences).__name__}"
            )
        return tuple(
            sorted(
                candidate_tuple,
                key=lambda candidate: confidences.get(candidate.name, 0.0),
                reverse=True,
            )
        )
