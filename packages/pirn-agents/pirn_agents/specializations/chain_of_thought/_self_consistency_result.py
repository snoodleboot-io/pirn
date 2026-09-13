"""``_SelfConsistencyResult`` — wrap the winning answer as an AgentResponse."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _SelfConsistencyResult(Knot):
    """Wrap the majority-vote answer string as an :class:`AgentResponse`."""

    def __init__(self, *, winner: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(winner=winner, _config=_config, **kwargs)

    async def process(self, winner: str, **_: Any) -> AgentResponse:
        """Return ``winner`` wrapped as an :class:`AgentResponse`."""
        return AgentResponse(content=winner)
