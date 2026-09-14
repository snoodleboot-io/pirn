"""``PlanReActFrame`` — lineage metadata for a :class:`PlanReActResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass(frozen=True)
class PlanReActFrame(PirnOpaqueValue):
    """Run-level facts for a plan-then-ReAct-per-step run.

    Carries everything about *how* the run proceeded without carrying the
    final answer itself — the frame half of the
    ``Payload[PlanReActFrame, AgentResponse]`` split (PIR-868).

    Attributes
    ----------
    plan:
        The ordered plan steps produced by the planner.
    step_responses:
        The :class:`AgentResponse` from the ReAct loop run for each step.
    """

    plan: tuple[str, ...]
    step_responses: tuple[AgentResponse, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "plan": list(self.plan),
            "step_responses": [response._pirn_audit_dict() for response in self.step_responses],
        }
