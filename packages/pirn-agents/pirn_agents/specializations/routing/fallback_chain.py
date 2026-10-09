"""``FallbackChain`` — invoke ordered candidates until one succeeds.

Algorithm:
    1. Receive the ``ordered`` candidates (confidence-descending), the tool
       ``arguments``, and the ``confidences`` mapping.
    2. Validate types at process time.
    3. Drive the candidates with a
       :class:`~pirn_agents.specializations.routing.fallback_loop.FallbackLoop`
       (``LoopSubTapestry``, ADR agents-speaks-core WS5b): each candidate is
       one real, individually-traceable
       :class:`~pirn_agents.specializations.routing.candidate_attempt.CandidateAttempt`
       invocation, skipping the call (no ``ToolInvocation``) when its
       confidence is below its ``min_confidence`` floor, or invoking the
       candidate's tool and folding the outcome in; once a candidate
       succeeds the loop stops, so a candidate past that point is never even
       scheduled.
    4. Return a typed :class:`FallbackResult` recording the outcome, the
       candidates attempted, and the candidates skipped.

By stopping at the first success and skipping sub-threshold candidates the chain
avoids the wasted invocations a naive "retry every candidate" baseline pays —
and, because each candidate is a real knot, every attempt now gets its own
engine ``Result``, history record, and lineage, where the original hid all of
them behind one knot's hand-rolled loop and an ``await tool.invoke(...)`` the
engine never saw.

References:
    - Anthropic (2024) "Building effective agents" — routing + fallback
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.routing.fallback_chain_result import FallbackChainResult
from pirn_agents.specializations.routing.fallback_chain_state import FallbackChainState
from pirn_agents.specializations.routing.fallback_loop import FallbackLoop
from pirn_agents.specializations.routing.route_candidate import RouteCandidate


class FallbackChain(AgentPipeline):
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
    ) -> Knot:
        """Build the candidate chain and return its result-extracting sink knot.

        Args:
            ordered: Candidates in confidence-descending order.
            arguments: Arguments passed to each invoked tool.
            confidences: Confidence per candidate name (missing = 0.0).

        Returns:
            The sink knot whose output is a :class:`FallbackResult`.

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

        initial = Parameter(
            "initial",
            FallbackChainState,
            default=FallbackChainState(
                ordered=candidate_tuple,
                arguments=arguments,
                confidences=confidences,
            ),
        )
        loop = FallbackLoop(
            state=initial,
            _config=KnotConfig(id="fallback_loop"),
        )
        return FallbackChainResult(state=loop, _config=KnotConfig(id="result"))
