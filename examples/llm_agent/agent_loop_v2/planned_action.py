"""``PlannedAction`` — which agent composite to run for this iteration.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedAction:
    action_type: str  # "llm_task" | "react" | "planner"
    name: str
