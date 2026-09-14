"""``PlanReActResult`` — the typed outcome of a Plan-ReAct run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.plan_react.plan_react_frame import PlanReActFrame
from pirn_agents.types.messaging.agent_response import AgentResponse


class PlanReActResult(AgentResult[PlanReActFrame, AgentResponse]):
    """Outcome of a plan-then-ReAct-per-step run.

    ``PlanReActResult`` is ``Payload[PlanReActFrame, AgentResponse]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the last step's :class:`AgentResponse` (the overall result), and
    ``metadata`` is the :class:`PlanReActFrame` carrying the plan and every
    step's response. The constructor takes the pattern's named fields (``plan``,
    ``step_responses``, ``final``); read them back as ``metadata.<field>`` and
    ``data``.
    """

    def __init__(
        self,
        plan: tuple[str, ...],
        step_responses: tuple[AgentResponse, ...],
        final: AgentResponse,
    ) -> None:
        frame = PlanReActFrame(plan=plan, step_responses=step_responses)
        super().__init__(metadata=frame, data=final)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["final"] = self._audit_form(self.data)
        return audit
