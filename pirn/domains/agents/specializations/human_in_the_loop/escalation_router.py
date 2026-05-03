"""``EscalationRouter`` — route low-confidence responses to human escalation.

A :class:`Knot` that inspects the confidence score attached to an
:class:`AgentResponse` (stored in ``response.usage["confidence"]``).
Responses with a score below ``threshold`` are routed to the human
escalation queue by returning ``None``; responses at or above the
threshold are passed through unchanged.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class EscalationRouter(Knot):
    """Route below-threshold AgentResponses to human escalation."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                "EscalationRouter: threshold must be a float, "
                f"got {type(threshold).__name__}"
            )
        self._threshold = float(threshold)
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse | None:
        """Pass through high-confidence responses; return None for escalation candidates.

        Args:
            response: The agent response to evaluate.

        Returns:
            The original AgentResponse if confidence >= threshold, else None to indicate escalation.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "EscalationRouter: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        confidence = response.usage.get("confidence")
        if confidence is None:
            return None
        if float(confidence) >= self._threshold:
            return response
        return None
