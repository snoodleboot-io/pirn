"""``ApprovalGate`` — pause pipeline execution and await human approval.

A :class:`Knot` that emits an approval-request record for the upstream
system and returns a boolean indicating whether execution was approved.
When ``auto_approve=True`` the gate always returns ``True`` without
emitting a request; this mode is intended for automated testing only.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class ApprovalGate(Knot):
    """Pause execution and emit an approval request; return approval bool."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        auto_approve: bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(auto_approve, bool):
            raise TypeError(
                "ApprovalGate: auto_approve must be a bool, "
                f"got {type(auto_approve).__name__}"
            )
        self._auto_approve = auto_approve
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> bool:
        """Emit an approval request record and return whether execution is approved.

        Args:
            response: The agent response pending approval.

        Returns:
            True if approved (always True when auto_approve=True), False otherwise.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "ApprovalGate: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        if self._auto_approve:
            return True
        return False
