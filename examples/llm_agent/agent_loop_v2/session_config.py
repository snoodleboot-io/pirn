"""``SessionConfig`` — the session's iteration budget and terminal knot id.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import ClassVar


class SessionConfig:
    """Fixed session limits read by the planner, the decider and the driver."""

    max_iterations_per_msg: ClassVar[int] = 4
    max_total_iterations: ClassVar[int] = 20
    session_complete_id: ClassVar[str] = "session_complete"
