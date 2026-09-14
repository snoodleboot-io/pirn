# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``MajorityVoteStrategy`` — the ``majority_vote`` consensus mechanism.

Builds a core :class:`~pirn.nodes.reduce_.Reduce` over the specialist
responses (whole-list ``combine`` form): groups them by ``content`` and folds
to the most common one, ties broken by first-seen order. It needs no LLM.

Previously built a bespoke :class:`~pirn_agents.specializations.multi_agent.consensus_majority_vote_picker.ConsensusMajorityVotePicker`
knot that did the same reduction inside its own ``process()``; that class
stays importable (it has its own direct unit tests and is not deleted — see
its module docstring), but this strategy no longer constructs it, since the
reduction is exactly what ``Reduce`` names (ADR agents-speaks-core WS5a).

Algorithm:
    1. Wrap the response mapping's values (order preserved) in a
       :class:`~pirn.core.parameter.Parameter`, so the already-resolved list
       re-enters the inner graph as a real node.
    2. Fold that list with :meth:`_combine`: count occurrences of each
       distinct ``content`` string, then return the first response (by
       mapping-insertion order) whose ``content`` matches the highest count.

Math:
    Given :math:`n` responses with distinct content values
    :math:`c_1, \\dots, c_m` and vote counts :math:`\\text{count}(c_j)`:

    $$
    c^{*} = \\operatorname*{arg\\,max}_{c_j} \\ \\text{count}(c_j)
    $$

    Ties in :math:`\\text{count}` are broken by the smallest first-seen index
    among the tied :math:`c_j`.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.multi_agent.consensus_strategy import ConsensusStrategy
from pirn_agents.types.messaging.agent_response import AgentResponse


class MajorityVoteStrategy(ConsensusStrategy):
    """Reduce responses by picking the most common ``content``."""

    def name(self) -> str:
        """Return the ``majority_vote`` selector name."""
        return "majority_vote"

    def build(
        self,
        *,
        responses: Mapping[str, AgentResponse],
        llm: LLMProvider,
    ) -> Knot:
        """Build a :class:`Reduce` that folds ``responses`` to the majority vote."""
        ordered = Parameter(
            "majority_vote_responses",
            list[AgentResponse],
            default=list(responses.values()),
        )
        return Reduce(
            of=ordered,
            combine=MajorityVoteStrategy._combine,
            _config=KnotConfig(id="consensus"),
        )

    @staticmethod
    def _combine(of: list[AgentResponse]) -> AgentResponse:
        """Return the response whose ``content`` appears most frequently.

        Args:
            of: The specialist responses, in first-seen order.

        Returns:
            The response with the most common ``content``; ties are broken
            by first-seen order.

        Raises:
            TypeError: If any item is not an :class:`AgentResponse`.
        """
        for response in of:
            if not isinstance(response, AgentResponse):
                raise TypeError(
                    "MajorityVoteStrategy: every response must be an "
                    f"AgentResponse, got {type(response).__name__}"
                )
        counter: Counter[str] = Counter(r.content for r in of)
        winning_content = counter.most_common(1)[0][0]
        for response in of:
            if response.content == winning_content:
                return response
        # Unreachable — counter was populated from `of`.
        return of[0]
