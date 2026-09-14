"""``MultiHopResultExtractor`` — normalise the synthesis stage's raw output.

Replaces the inline ``_ResultSource(Source)`` that closed over an
already-computed :class:`AgentResponse` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass). The
normalisation itself runs inside this knot's ``process()``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class MultiHopResultExtractor(Knot):
    """Wrap the synthesis stage's raw output as an :class:`AgentResponse` if it is not one."""

    def __init__(
        self,
        *,
        raw: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(raw=raw, _config=_config, **kwargs)

    async def process(self, raw: Any, **_: Any) -> AgentResponse:
        """Return ``raw`` unchanged if it is already an :class:`AgentResponse`, else a fallback.

        Args:
            raw: The synthesis stage's raw output.

        Returns:
            ``raw`` if it is already an :class:`AgentResponse`, else an
            empty response marked ``finish_reason="length"``.
        """
        if isinstance(raw, AgentResponse):
            return raw
        return AgentResponse(content="", finish_reason="length")
