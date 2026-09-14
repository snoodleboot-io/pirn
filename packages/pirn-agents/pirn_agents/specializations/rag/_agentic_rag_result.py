"""``AgenticRagResult`` — extract the final answer from loop state."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.rag._agentic_rag_state import AgenticRagState
from pirn_agents.types.messaging.agent_response import AgentResponse


class AgenticRagResult(Knot):
    """Extract the final answer from the loop's final state."""

    def __init__(
        self,
        *,
        state: Knot | AgenticRagState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: AgenticRagState, **_: Any) -> AgentResponse:
        """Return the last round's answer as an :class:`AgentResponse`."""
        return AgentResponse(content=state.answer, finish_reason="stop")
