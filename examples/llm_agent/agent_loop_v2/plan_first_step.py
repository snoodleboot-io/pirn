"""``_PlanFirstStep`` — extracts the first step string from a ``Plan``.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn_agents.planning.plan import Plan


class _PlanFirstStep(Knot):
    """Extract the first step string from a ``Plan`` for ``ToolRouter``."""

    async def process(self, plan: Any, **_: Any) -> str:
        if isinstance(plan, Plan) and plan.steps:
            return plan.steps[0]
        return str(plan)
