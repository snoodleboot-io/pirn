"""``_CandidateResponse`` — wrap a candidate as an AgentResponse, behind a gate.

``ReflectionCheck`` consumes an :class:`AgentResponse`, and must only be
consulted when the accept gate did *not* fire — otherwise an accepted run pays
an extra LLM call it never used to.

``Gate`` passes through a single parent, so it cannot itself feed the two inputs
``ReflectionCheck`` needs. This knot is the join: it takes the candidate and the
gate's pass-through, so when the gate is ``Skipped`` this knot is skipped, and
the reflection check downstream of it is skipped too.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class _CandidateResponse(Knot):
    """Present a candidate string as an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        candidate: Knot | str,
        gate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(candidate=candidate, gate=gate, _config=_config, **kwargs)

    async def process(self, candidate: str, **_: Any) -> AgentResponse:
        """Wrap ``candidate``.

        Args:
            candidate: The candidate answer text.

        Returns:
            An :class:`AgentResponse` carrying the candidate.
        """
        return AgentResponse(content=candidate)
