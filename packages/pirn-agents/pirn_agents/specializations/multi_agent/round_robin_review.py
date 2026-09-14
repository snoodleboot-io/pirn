"""``RoundRobinReview`` — iterative multi-reviewer refinement.

A :class:`SubTapestry` that passes a draft :class:`AgentResponse`
through N reviewer agents in order, each receiving the previous
agent's output as its input. Returns the final revised response.

Reviewers accept a ``response: AgentResponse`` and produce a revised one. Each
round runs through :class:`ReviewerInvocation`, which itself delegates
through :meth:`SpecialistHandle.run` — the reviewer's
``__call__``, never its ``process()`` (a :class:`SubTapestry`'s ``process()``
only *builds* the sink knot of its inner pipeline; calling it directly used to
mean every review was silently discarded, see PIR-769).

Algorithm
---------
1. Validate inputs.
2. Drive the reviewer sequence with a :class:`RoundRobinLoop`
   (``LoopSubTapestry``): each round is one real, individually-traceable
   ``ReviewerInvocation`` knot rather than a step inside a hand-rolled Python
   ``for`` loop (ADR agents-speaks-core WS5a).
3. Extract the final revised response with :class:`RoundRobinResponseExtractor`.

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
from pirn.core.parameter import Parameter

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent._round_robin_loop import RoundRobinLoop
from pirn_agents.specializations.multi_agent._round_robin_response_extractor import (
    RoundRobinResponseExtractor,
)
from pirn_agents.specializations.multi_agent._round_robin_state import RoundRobinState
from pirn_agents.types.messaging.agent_response import AgentResponse


class RoundRobinReview(AgentPipeline):
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
    ) -> Knot:
        """Send the draft through each reviewer in round-robin order, returning the final result.

        Args:
            response: The initial draft AgentResponse to be reviewed.
            reviewers: A non-empty sequence of SubTapestry reviewer agents.

        Returns:
            The sink knot whose output is the AgentResponse produced by the
            last reviewer in the sequence.

        Raises:
            ValueError: If reviewers is empty.
        """
        reviewer_list = list(reviewers)
        if not reviewer_list:
            raise ValueError("RoundRobinReview: reviewers must be a non-empty sequence")

        initial = Parameter(
            "rrr_state",
            RoundRobinState,
            default=RoundRobinState(response=response, index=0),
        )
        loop = RoundRobinLoop(
            reviewers=reviewer_list,
            state=initial,
            _config=KnotConfig(id="rrr_loop"),
        )
        return RoundRobinResponseExtractor(
            state=loop,
            _config=KnotConfig(id="final"),
        )
