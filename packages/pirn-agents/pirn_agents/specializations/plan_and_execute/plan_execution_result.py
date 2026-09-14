"""``PlanExecutionResult`` — assemble the final ``AgentResponse`` from loop state."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.plan_and_execute.plan_step_state import PlanStepState
from pirn_agents.types.messaging.agent_response import AgentResponse


class PlanExecutionResult(Knot):
    """Concatenate every step's result into the plan's final ``AgentResponse``."""

    def __init__(
        self,
        *,
        state: Knot | PlanStepState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: PlanStepState, **_: Any) -> AgentResponse:
        """Return an ``AgentResponse`` whose content lists every step's result."""
        combined = "\n".join(f"Step {i + 1}: {r}" for i, r in enumerate(state.step_results))
        return AgentResponse(content=combined)
