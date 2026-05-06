"""``EscalationRouter`` — route low-confidence responses to human escalation.

A :class:`Knot` that inspects the confidence score attached to an
:class:`AgentResponse` (stored in ``response.usage["confidence"]``).
Responses with a score below ``threshold`` are routed to the human
escalation queue by returning ``None``; responses at or above the
threshold are passed through unchanged.

Algorithm:
    1. Receive the resolved ``response`` (AgentResponse) and ``threshold`` (float).
    2. Validate that ``response`` is an AgentResponse instance.
    3. Read ``response.usage["confidence"]``; if absent, return None (escalate).
    4. Cast confidence to float and compare against threshold.
    5. Return the response unchanged if confidence >= threshold, else return None.


References:
    - Madaan et al. (2023) "Self-Refine: Iterative Refinement with Self-Feedback"
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
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        threshold: float = 0.8,
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
        if float(confidence) >= float(threshold):
            return response
        return None
