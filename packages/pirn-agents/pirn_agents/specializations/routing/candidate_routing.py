"""``CandidateRouting`` — the ``Payload`` a candidate ordering hands back.

``CandidateRouting`` is ``AgentResult[CandidateRoutingFrame, tuple[RouteCandidate, ...]]``
(PIR-874, following PIR-868): ``data`` is the candidates in confidence order —
:class:`~pirn_agents.specializations.routing.route_candidate.RouteCandidate` is
a record the whole routing family passes around and stays one — and
``metadata`` records the order by name and the confidences it was made from.
A bare tuple crossing the boundary between
:class:`~pirn_agents.specializations.routing.candidate_router.CandidateRouter`
and :class:`~pirn_agents.specializations.routing.fallback_chain.FallbackChain`
said nothing about why it was in that order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.routing.candidate_routing_frame import CandidateRoutingFrame
from pirn_agents.specializations.routing.route_candidate import RouteCandidate


class CandidateRouting(AgentResult[CandidateRoutingFrame, tuple[RouteCandidate, ...]]):
    """Route candidates in the order they should be tried."""

    def __init__(
        self,
        ordered: Sequence[RouteCandidate],
        confidences: Mapping[str, float] | None = None,
    ) -> None:
        candidates = tuple(ordered)
        frame = CandidateRoutingFrame(
            order=tuple(candidate.name for candidate in candidates),
            confidences=dict(confidences or {}),
        )
        super().__init__(metadata=frame, data=candidates)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["candidates"] = self._audit_forms(self.data)
        return audit
