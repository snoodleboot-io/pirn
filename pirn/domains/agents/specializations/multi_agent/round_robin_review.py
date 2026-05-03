"""``RoundRobinReview`` — iterative multi-reviewer refinement.

A :class:`SubTapestry` that passes a draft :class:`AgentResponse`
through N reviewer agents in order, each receiving the previous
agent's output as its input. Returns the final revised response.

Reviewers must expose ``process(response: AgentResponse, **_) -> AgentResponse``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry


class RoundRobinReview(SubTapestry):
    """Pass a draft response sequentially through N reviewer agents."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        reviewers: Sequence[SubTapestry],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not reviewers:
            raise ValueError(
                "RoundRobinReview: reviewers must be a non-empty sequence"
            )
        for index, reviewer in enumerate(reviewers):
            if not isinstance(reviewer, SubTapestry):
                raise TypeError(
                    f"RoundRobinReview: reviewers[{index}] must be a "
                    f"SubTapestry, got {type(reviewer).__name__}"
                )
        self._reviewers = list(reviewers)
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse:
        """Send the draft through each reviewer in round-robin order, returning the final result.

        Args:
            response: The initial draft AgentResponse to be reviewed.

        Returns:
            The AgentResponse produced by the last reviewer in the sequence.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "RoundRobinReview: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        current = response
        for reviewer in self._reviewers:
            result = await reviewer.process(response=current)
            if isinstance(result, AgentResponse):
                current = result
        return current
