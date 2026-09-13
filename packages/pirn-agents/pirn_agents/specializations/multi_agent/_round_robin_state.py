"""``_RoundRobinState`` — the value threaded through the reviewer loop.

Internal API. See ``_round_robin_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass(frozen=True)
class _RoundRobinState:
    """One iteration's worth of accumulated round-robin review state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        response: The response as revised by every reviewer up to and
            including the last completed iteration.
        index: How many reviewers have already run (0-based cursor into the
            reviewer sequence held by ``_RoundRobinLoop``).
    """

    response: AgentResponse
    index: int
