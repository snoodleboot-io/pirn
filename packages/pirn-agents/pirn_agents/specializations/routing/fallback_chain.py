"""``FallbackChain`` — invoke ordered candidates until one succeeds.

Algorithm:
    1. Receive the ``ordered`` candidates (confidence-descending), the tool
       ``arguments``, and the ``confidences`` mapping.
    2. Validate types at process time.
    3. Build a static chain of one :class:`_CandidateAttempt` knot per
       candidate: each skips its candidate (no call attempted) when its
       confidence is below its ``min_confidence`` floor, or when an earlier
       candidate already succeeded; otherwise it invokes the candidate's tool
       via a real :class:`~pirn_agents.tools.tool_invocation.ToolInvocation`
       and folds the outcome in.
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
from dataclasses import dataclass
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.routing.fallback_result import FallbackResult
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus


@dataclass
class _FallbackChainState:
    """State threaded across fallback candidates."""

    attempted: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    succeeded_result: ToolResult | None = None
    chosen: str | None = None
    locked: bool = False


class _FoldCandidateResult(Knot):
    """Fold one candidate's :class:`ToolResult` into the chain's state."""

    def __init__(
        self,
        *,
        prior: Knot | _FallbackChainState,
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
        prior: _FallbackChainState,
        candidate: RouteCandidate,
        tool_result: ToolResult,
        **_: Any,
    ) -> _FallbackChainState:
        """Record ``candidate`` as attempted, locking the chain on success."""
        attempted = (*prior.attempted, candidate.name)
        if tool_result.status is ToolStatus.OK:
            return _FallbackChainState(
                attempted=attempted,
                skipped=prior.skipped,
                succeeded_result=tool_result,
                chosen=candidate.name,
                locked=True,
            )
        return _FallbackChainState(attempted=attempted, skipped=prior.skipped)


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


class _FallbackChainResult(Knot):
    """Extract the final :class:`FallbackResult` from the chain's state."""

    def __init__(
        self, *, state: Knot | _FallbackChainState, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _FallbackChainState, **_: Any) -> FallbackResult:
        """Return the successful result, or an exhausted-chain result."""
        return FallbackResult(
            succeeded=state.chosen is not None,
            chosen=state.chosen,
            result=state.succeeded_result,
            attempted=state.attempted,
            skipped=state.skipped,
        )


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
