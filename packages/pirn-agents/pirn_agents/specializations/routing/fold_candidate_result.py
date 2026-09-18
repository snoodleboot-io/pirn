"""``FoldCandidateResult`` — fold one candidate's ToolResult into state."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing.fallback_chain_state import FallbackChainState
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.tools.tool_result import ToolResult


class FoldCandidateResult(Knot):
    """Fold one candidate's :class:`ToolResult` into the chain's state."""

    def __init__(
        self,
        *,
        prior: Knot | FallbackChainState,
        candidate: Knot | RouteCandidate,
        tool_result: Knot | ToolResult,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior, candidate=candidate, tool_result=tool_result, _config=_config, **kwargs
        )

    async def process(
        self,
        prior: FallbackChainState,
        candidate: RouteCandidate,
        tool_result: ToolResult,
        **_: Any,
    ) -> FallbackChainState:
        """Record ``candidate`` as attempted, locking the chain on success."""
        attempted = (*prior.attempted, candidate.name)
        if tool_result.succeeded:
            return replace(
                prior,
                attempted=attempted,
                succeeded_result=tool_result,
                chosen=candidate.name,
                locked=True,
            )
        return replace(prior, attempted=attempted)
