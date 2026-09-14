"""``ConsensusMajorityVotePicker`` — pick the most common response by content.

No longer built by :class:`~pirn_agents.specializations.multi_agent.majority_vote_strategy.MajorityVoteStrategy`
(ADR agents-speaks-core WS5a): that strategy now folds the same reduction
through a core :class:`~pirn.nodes.reduce_.Reduce`, since "reduce a list to
one value" is exactly what ``Reduce`` names, and a bespoke Knot doing the
identical fold inside its own ``process()`` duplicates it. This class is kept
— it is directly unit-tested and its public name stays importable — but is no
longer part of ``ConsensusPipeline``'s wiring.

Groups responses by their ``content`` field and returns the response whose
content appears most frequently. Ties are broken by first-seen order.

Algorithm:
    1. Preserve insertion order of responses via :class:`OrderedDict`.
    2. Count occurrences of each unique ``content`` string.
    3. Select the content with the highest count (first-seen wins ties).
    4. Return the first :class:`AgentResponse` whose content matches.

Math:
    Given :math:`n` responses with distinct content values
    :math:`c_1, \\dots, c_m` and vote counts :math:`\\text{count}(c_j)` (the
    number of responses whose content equals :math:`c_j`):

    $$
    c^{*} = \\operatorname*{arg\\,max}_{c_j} \\ \\text{count}(c_j)
    $$

    Ties in :math:`\\text{count}` are broken by the smallest first-seen index
    among the tied :math:`c_j` — :class:`collections.Counter.most_common`
    preserves insertion order for equal counts, and the input is walked in
    the caller-supplied ``responses`` order.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class ConsensusMajorityVotePicker(Knot):
    """Picks the :class:`AgentResponse` with the most common ``content``."""

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(responses=responses, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        **_: Any,
    ) -> AgentResponse:
        """Return the AgentResponse whose content appears most frequently among the inputs.

        Args:
            responses: A non-empty mapping of specialist names to AgentResponse instances.

        Returns:
            The AgentResponse whose content appears most often; ties are broken by first-seen order.

        Raises:
            ValueError: If responses is empty or not a Mapping.
            TypeError: If any value in responses is not an AgentResponse.
        """
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError("ConsensusMajorityVotePicker: responses must be a non-empty mapping")
        ordered: OrderedDict[str, AgentResponse] = OrderedDict()
        for name, response in responses.items():
            if not isinstance(response, AgentResponse):
                raise TypeError(
                    "ConsensusMajorityVotePicker: every response must be an "
                    f"AgentResponse, got {type(response).__name__} for {name!r}"
                )
            ordered[name] = response
        counter: Counter[str] = Counter(r.data for r in ordered.values())
        winning_content = counter.most_common(1)[0][0]
        for response in ordered.values():
            if response.data == winning_content:
                return response
        # Unreachable — Counter populated from ordered values.
        return next(iter(ordered.values()))
