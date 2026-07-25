"""``RouterFallbackPipeline`` — confidence router wired to a typed fallback chain.

A :class:`SubTapestry` that wires, as a static inner tapestry:

1. :class:`CandidateRouter` — orders the typed candidates best-first by
   confidence.
2. :class:`FallbackChain` — invokes them in that order, skipping sub-threshold
   candidates and stopping at the first success.

The result is a typed :class:`FallbackResult`. Dispatching best-first and
stopping on first success avoids the wasted retries a naive "try every candidate"
baseline pays.

Algorithm:
    1. Validate ``candidates`` (each a RouteCandidate), ``confidences`` (Mapping),
       and ``arguments`` (Mapping).
    2. Wire router -> chain and return the chain sink.

References:
    - Anthropic (2024) "Building effective agents" — routing + fallback
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.routing.candidate_router import CandidateRouter
from pirn_agents.specializations.routing.fallback_chain import FallbackChain
from pirn_agents.specializations.routing.route_candidate import RouteCandidate


class RouterFallbackPipeline(SubTapestry):
    """Confidence router + typed fallback chain over :class:`RouteCandidate`s."""

    def __init__(
        self,
        *,
        candidates: Knot | Sequence[RouteCandidate],
        confidences: Knot | Mapping[str, float],
        arguments: Knot | Mapping[str, Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            candidates=candidates,
            confidences=confidences,
            arguments=arguments,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        candidates: Sequence[RouteCandidate],
        confidences: Mapping[str, float],
        arguments: Mapping[str, Any],
        **_: Any,
    ) -> Any:
        """Wire the router + fallback chain and return the chain sink.

        Args:
            candidates: Typed routing candidates.
            confidences: Confidence per candidate name.
            arguments: Arguments passed to the invoked tool.

        Returns:
            The :class:`FallbackChain` sink whose output is a
            :class:`FallbackResult`.

        Raises:
            TypeError: If any input has the wrong type.
        """
        candidate_tuple = tuple(candidates)
        for index, candidate in enumerate(candidate_tuple):
            if not isinstance(candidate, RouteCandidate):
                raise TypeError(
                    f"RouterFallbackPipeline: candidates[{index}] must be a RouteCandidate, got "
                    f"{type(candidate).__name__}"
                )
        if not isinstance(confidences, Mapping):
            raise TypeError(
                "RouterFallbackPipeline: confidences must be a Mapping, got "
                f"{type(confidences).__name__}"
            )
        if not isinstance(arguments, Mapping):
            raise TypeError(
                "RouterFallbackPipeline: arguments must be a Mapping, got "
                f"{type(arguments).__name__}"
            )
        router = CandidateRouter(
            candidates=candidate_tuple,
            confidences=confidences,
            _config=KnotConfig(id="route_order", validate_io=False),
        )
        return FallbackChain(
            ordered=router,
            arguments=arguments,
            confidences=confidences,
            _config=KnotConfig(id="fallback_chain", validate_io=False),
        )
