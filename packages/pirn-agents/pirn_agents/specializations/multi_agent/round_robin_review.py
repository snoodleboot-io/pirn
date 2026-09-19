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
2. Wire one :class:`ReviewerInvocation` knot per reviewer at build time, each
   taking the previous invocation as its ``response`` input, so the engine owns
   the ordering and every round is individually traceable (ADR
   agents-speaks-core WS5a, revised by PIR-873). Every reviewer always runs and
   the count is fixed at construction, so there is nothing for a
   ``LoopSubTapestry`` to decide; a loop here only added a state object, an
   inner run per round, and inputs held on the loop instance.
3. Return the last invocation as the sink: its output is the final response.

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

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent.reviewer_invocation import ReviewerInvocation
from pirn_agents.specializations.multi_agent.specialist_handle import SpecialistHandle
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
            The last reviewer's :class:`ReviewerInvocation`, whose output is the
            final revised response. Each reviewer takes the previous one as its
            ``response`` input, so the engine owns the ordering.

        Raises:
            ValueError: If reviewers is empty.
        """
        reviewer_list = list(reviewers)
        if not reviewer_list:
            raise ValueError("RoundRobinReview: reviewers must be a non-empty sequence")

        current: Knot | AgentResponse = response
        for index, reviewer in enumerate(reviewer_list):
            current = ReviewerInvocation(
                reviewer=SpecialistHandle(specialist=reviewer),
                response=current,
                _config=KnotConfig(id=f"review_{index}"),
            )
        return current
