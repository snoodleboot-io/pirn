"""``FlareResultExtractor`` — assemble the final :class:`AgentResponse`.

Replaces the inline ``_ResultSource(Source)`` that closed over an
already-computed :class:`AgentResponse` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.rag.flare_state import FlareState
from pirn_agents.types.messaging.agent_response import AgentResponse


class FlareResultExtractor(Knot):
    """Join the loop's accumulated sentences into the final :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: FlareState, **_: Any) -> AgentResponse:
        """Join the loop's accumulated sentence parts into the final response.

        Args:
            state: The loop's final accumulated state.

        Returns:
            An :class:`AgentResponse` whose content is every generated
            sentence joined with a single space.
        """
        return AgentResponse(content=" ".join(state.parts), finish_reason="stop")
