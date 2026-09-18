"""``StepResult`` — one completed action inside a session iteration.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepResult:
    iteration: int
    msg_idx: int
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str
    output: str
