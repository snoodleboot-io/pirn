"""``PlannedAction`` — one action the planner chose for this iteration.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedAction:
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str
    args: dict
