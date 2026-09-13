"""``FallbackChain`` — invoke ordered candidates until one succeeds.

Algorithm:
    1. Receive the ``ordered`` candidates (confidence-descending), the tool
       ``arguments``, and the ``confidences`` mapping.
    2. Validate types at process time.
    3. Build a static chain of one
       :class:`~pirn_agents.specializations.routing._candidate_attempt._CandidateAttempt`
       knot per candidate: each skips its candidate (no call attempted) when
       its confidence is below its ``min_confidence`` floor, or when an
       earlier candidate already succeeded; otherwise it invokes the
       candidate's tool via a real
       :class:`~pirn_agents.tools.tool_invocation.ToolInvocation` and folds
       the outcome in.
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

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.routing._candidate_attempt import _CandidateAttempt
from pirn_agents.specializations.routing._fallback_chain_result import _FallbackChainResult
from pirn_agents.specializations.routing._fallback_chain_state import _FallbackChainState
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

        chain: Knot = ResolvedValueKnot(
            value=_FallbackChainState(), _config=KnotConfig(id="initial")
        )
        for index, candidate in enumerate(candidate_tuple):
            chain = _CandidateAttempt(
                prior=chain,
                candidate=candidate,
                arguments=arguments,
                confidences=confidences,
                _config=KnotConfig(id=f"attempt_{index}"),
            )
        return _FallbackChainResult(state=chain, _config=KnotConfig(id="result"))
