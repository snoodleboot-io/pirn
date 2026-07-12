"""``PlanReActResult`` — the typed outcome of a Plan-ReAct run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.agent_response import AgentResponse


@dataclass(frozen=True)
class PlanReActResult(PirnOpaqueValue):
    """Outcome of a plan-then-ReAct-per-step run.

    Attributes
    ----------
    plan:
        The ordered plan steps produced by the planner.
    step_responses:
        The :class:`AgentResponse` from the ReAct loop run for each step.
    final:
        The last step's :class:`AgentResponse` (the overall result).
    """

    plan: tuple[str, ...]
    step_responses: tuple[AgentResponse, ...]
    final: AgentResponse

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "plan": list(self.plan),
            "step_responses": [response._pirn_audit_dict() for response in self.step_responses],
            "final": self.final._pirn_audit_dict(),
        }
