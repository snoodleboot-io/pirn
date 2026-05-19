"""``RoundRobinReview`` — iterative multi-reviewer refinement.

A :class:`SubTapestry` that passes a draft :class:`AgentResponse`
through N reviewer agents in order, each receiving the previous
agent's output as its input. Returns the final revised response.

Reviewers must expose ``process(response: AgentResponse, **_) -> AgentResponse``.

Algorithm
---------
1. Validate inputs.
2. Iterate over reviewers sequentially; each sees the previous output.
3. Wrap the final result in a pass-through inner tapestry via
   :class:`_ResponseEcho` so that the SubTapestry contract is honoured.
4. Return the final reviewed AgentResponse.

Math
----
N/A — no quantitative computation.

References
----------
N/A — pirn-native implementation only.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry


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


class RoundRobinReview(SubTapestry):
    """Pass a draft response sequentially through N reviewer agents."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        reviewers: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, reviewers=reviewers, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        reviewers: Any,
        **_: Any,
    ) -> Any:
        """Send the draft through each reviewer in round-robin order, returning the final result.

        Args:
            response: The initial draft AgentResponse to be reviewed.
            reviewers: A non-empty sequence of SubTapestry reviewer agents.

        Returns:
            The AgentResponse produced by the last reviewer in the sequence.

        Raises:
            TypeError: If response is not an AgentResponse instance.
            ValueError: If reviewers is empty.
        """
        reviewer_list = list(reviewers)
        if not reviewer_list:
            raise ValueError("RoundRobinReview: reviewers must be a non-empty sequence")
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "RoundRobinReview: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        current = response
        for reviewer in reviewer_list:
            result = await reviewer.process(response=current)
            if isinstance(result, AgentResponse):
                current = result
        return _ResponseEcho(
            response=current,
            _config=KnotConfig(id="final"),
        )
