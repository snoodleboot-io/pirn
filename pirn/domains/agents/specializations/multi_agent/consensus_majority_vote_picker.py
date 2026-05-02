"""``ConsensusMajorityVotePicker`` — pick the most common response by content.

Inner stage knot used by :class:`ConsensusAggregator` when the
``majority_vote`` strategy is selected. Groups responses by their
``content`` field and returns the response whose content appears most
frequently. Ties are broken by first-seen order.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


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
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError(
                "ConsensusMajorityVotePicker: responses must be a "
                "non-empty mapping"
            )
        ordered: OrderedDict[str, AgentResponse] = OrderedDict()
        for name, response in responses.items():
            if not isinstance(response, AgentResponse):
                raise TypeError(
                    "ConsensusMajorityVotePicker: every response must be an "
                    f"AgentResponse, got {type(response).__name__} for {name!r}"
                )
            ordered[name] = response
        counter: Counter[str] = Counter(
            r.content for r in ordered.values()
        )
        winning_content = counter.most_common(1)[0][0]
        for response in ordered.values():
            if response.content == winning_content:
                return response
        # Unreachable — Counter populated from ordered values.
        return next(iter(ordered.values()))
