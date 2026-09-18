"""``StepResult`` — one agent composite's ``AgentResponse``, tagged with its position.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass(frozen=True)
class StepResult:
    iteration: int
    msg_idx: int
    action_type: str  # "llm_task" | "react" | "planner"
    name: str
    response: AgentResponse
