"""``_CandidateAttempt`` — skip, or invoke, one fallback candidate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.routing._fallback_chain_state import _FallbackChainState
from pirn_agents.specializations.routing._fold_candidate_result import _FoldCandidateResult
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation


class _CandidateAttempt(AgentPipeline):
    """Skip, or invoke, one candidate depending on the chain's state so far.

    The inner graph's shape depends on the resolved ``prior``/``confidences``
    values (skip vs. invoke), per the ``MultiSourceLoader`` pattern in
    ``docs/guides/sub-tapestry.md`` §4 — a real ``ToolInvocation`` node is
    built only when this candidate is actually going to be called, so a
    locked-out or sub-threshold candidate never pays for one.
    """

    def __init__(
        self,
        *,
        prior: Knot | _FallbackChainState,
        candidate: Knot | RouteCandidate,
        arguments: Knot | Mapping[str, Any],
        confidences: Knot | Mapping[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior,
            candidate=candidate,
            arguments=arguments,
            confidences=confidences,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prior: _FallbackChainState,
        candidate: RouteCandidate,
        arguments: Mapping[str, Any],
        confidences: Mapping[str, float],
        **_: Any,
    ) -> Knot:
        """Build the skip or invoke-and-fold graph for this candidate.

        Args:
            prior: The chain's accumulated state before this candidate.
            candidate: This candidate's name, tool, and confidence floor.
            arguments: Arguments passed to the tool if invoked.
            confidences: Confidence per candidate name (missing = 0.0).

        Returns:
            The sink knot whose output is the updated chain state.
        """
        if prior.locked:
            return ResolvedValueKnot(value=prior, _config=KnotConfig(id="locked"))
        if confidences.get(candidate.name, 0.0) < candidate.min_confidence:
            return ResolvedValueKnot(
                value=_FallbackChainState(
                    attempted=prior.attempted, skipped=(*prior.skipped, candidate.name)
                ),
                _config=KnotConfig(id="skip"),
            )
        call = ToolCall(tool_name=candidate.tool.name, arguments=arguments, call_id=candidate.name)
        invoke = ToolInvocation(tool=candidate.tool, call=call, _config=KnotConfig(id="call"))
        return _FoldCandidateResult(
            prior=prior, candidate=candidate, tool_result=invoke, _config=KnotConfig(id="fold")
        )
