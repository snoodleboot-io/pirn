"""``_TreeOfThoughtResult`` — extract the best-scoring path from the beam."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _TreeOfThoughtResult(Knot):
    """Extract the best-scoring path from the final beam."""

    def __init__(
        self,
        *,
        beam: Knot | list[tuple[str, float]],
        prompt: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(beam=beam, prompt=prompt, _config=_config, **kwargs)

    async def process(self, beam: list[tuple[str, float]], prompt: str, **_: Any) -> AgentResponse:
        """Return the top beam entry's path as an :class:`AgentResponse`."""
        best_path = beam[0][0] if beam else prompt
        return AgentResponse(content=best_path)
