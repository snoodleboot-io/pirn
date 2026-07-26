"""``_ResponseEcho`` — pass-through knot for the SubTapestry contract.

Wraps an already-computed :class:`AgentResponse` so that a SubTapestry can
honour its ``process(**) -> Knot`` contract without recomputing anything: the
knot simply returns the response it was given.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _ResponseEcho(Knot):
    """Pass-through knot that returns the supplied AgentResponse unchanged."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(self, response: AgentResponse, **_: Any) -> AgentResponse:
        return response
