"""``_ToolResultWrapper`` — turns a ``ToolResult`` into an ``AgentResponse``.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn_agents.types.messaging.agent_response import AgentResponse


class _ToolResultWrapper(Knot):
    """Convert a ToolResult to an AgentResponse for the outer aggregator."""

    async def process(self, exec_out: Any, **_: Any) -> AgentResponse:
        tool_content = (
            str(exec_out.result)
            if exec_out and exec_out.error is None
            else (str(exec_out.error) if exec_out else "[planner: no output]")
        )
        return AgentResponse(content=f"[plan→tool] {tool_content}")
