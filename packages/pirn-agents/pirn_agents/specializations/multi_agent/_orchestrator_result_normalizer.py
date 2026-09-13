"""``_OrchestratorResultNormalizer`` — normalise a specialist's raw output.

Replaces the inline ``_ResultSource(Source)`` that closed over an
already-computed :class:`AgentResponse` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass). The
normalisation itself (wrap a bare value as an :class:`AgentResponse` when the
specialist did not already return one) runs inside this knot's ``process()``,
so it is a real, individually-traceable knot rather than a ``Source`` handing
back an answer Python already had.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _OrchestratorResultNormalizer(Knot):
    """Wrap a specialist's raw output as an :class:`AgentResponse` if it is not one."""

    def __init__(
        self,
        *,
        raw: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(raw=raw, _config=_config, **kwargs)

    async def process(self, raw: Any, **_: Any) -> AgentResponse:
        """Return ``raw`` unchanged if it is already an :class:`AgentResponse`, else wrap it.

        Args:
            raw: The specialist's raw output.

        Returns:
            ``raw`` if it is already an :class:`AgentResponse`, else a new
            one wrapping its string form.
        """
        return (
            raw
            if isinstance(raw, AgentResponse)
            else AgentResponse(content=str(raw), finish_reason="stop")
        )
