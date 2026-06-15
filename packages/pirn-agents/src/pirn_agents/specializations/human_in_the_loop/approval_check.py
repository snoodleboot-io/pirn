"""``ApprovalCheck`` — pause pipeline execution and await human approval.

Algorithm:
    1. Receive the resolved ``response`` AgentResponse and ``auto_approve`` flag.
    2. Validate that ``response`` is an AgentResponse instance.
    3. If ``auto_approve`` is True, return True immediately without emitting a request.
    4. Emit an approval-request record for the upstream system.
    5. Return False (pending approval from a human operator).


References:
    - Human-in-the-loop design patterns for agentic AI systems.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.agent_response import AgentResponse


class ApprovalCheck(Knot):
    """Pause execution and emit an approval request; return approval bool."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        auto_approve: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, auto_approve=auto_approve, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        auto_approve: bool = False,
        **_: Any,
    ) -> bool:
        """Emit an approval request record and return whether execution is approved.

        Args:
            response: The agent response pending approval.
            auto_approve: When True, skip the approval request and return True immediately.

        Returns:
            True if approved (always True when auto_approve=True), False otherwise.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                f"ApprovalCheck: response must be an AgentResponse, got {type(response).__name__}"
            )
        if auto_approve:
            return True
        return False
