"""``PlanReActResultExtractor`` — surface the plan+ReAct run's :class:`PlanReActResult`.

Replaces the inline ``_PlanReActResultSource(Source)`` that closed over an
already-computed :class:`PlanReActResult` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass). Pure
extraction — no LLM/tool call here.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.plan_react.plan_react_result import PlanReActResult
from pirn_agents.types.messaging.agent_response import AgentResponse


class PlanReActResultExtractor(Knot):
    """Wrap the already-computed plan and per-step responses as a :class:`PlanReActResult`."""

    def __init__(
        self,
        *,
        plan: tuple[str, ...],
        step_responses: tuple[AgentResponse, ...],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(plan=plan, step_responses=step_responses, _config=_config, **kwargs)

    async def process(
        self, plan: tuple[str, ...], step_responses: tuple[AgentResponse, ...], **_: Any
    ) -> PlanReActResult:
        """Return the :class:`PlanReActResult` for the whole run.

        Args:
            plan: The (possibly capped) ordered plan steps that were executed.
            step_responses: Each step's :class:`AgentResponse`, in order.

        Returns:
            The :class:`PlanReActResult`, whose ``final`` is the last step's
            response (or an empty response when no step ran).
        """
        final = step_responses[-1] if step_responses else AgentResponse(content="")
        return PlanReActResult(plan=plan, step_responses=step_responses, final=final)
