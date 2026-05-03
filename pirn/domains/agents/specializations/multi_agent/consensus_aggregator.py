"""``ConsensusAggregator`` — fuse multiple :class:`AgentResponse`s.

A :class:`SubTapestry` that takes a mapping of specialist responses
and produces a single consensus :class:`AgentResponse`. Two
strategies are supported:

* ``"majority_vote"`` — group responses by their ``content`` and
  return the most common one. Ties are broken by first-seen order.
* ``"llm_synthesis"`` — feed every response into an LLM and return its
  synthesised reply.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.multi_agent.consensus_majority_vote_picker import (
    ConsensusMajorityVotePicker,
)
from pirn.domains.agents.specializations.multi_agent.consensus_synthesis_caller import (
    ConsensusSynthesisCaller,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ConsensusAggregator(SubTapestry):
    """Reduces specialist responses to one :class:`AgentResponse`."""

    _supported_strategies: tuple[str, ...] = (
        "majority_vote",
        "llm_synthesis",
    )

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        llm: LLMProvider,
        _config: KnotConfig,
        strategy: str = "llm_synthesis",
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ConsensusAggregator: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if strategy not in self._supported_strategies:
            raise ValueError(
                "ConsensusAggregator: strategy must be one of "
                f"{self._supported_strategies!r}, got {strategy!r}"
            )
        self._llm = llm
        self._strategy = strategy
        super().__init__(responses=responses, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        **_: Any,
    ) -> AgentResponse:
        """Apply the configured consensus strategy to the specialist responses and return the winner.

        Args:
            responses: A non-empty mapping of specialist names to their AgentResponse outputs.

        Returns:
            A single AgentResponse representing the consensus result.

        Raises:
            ValueError: If responses is empty or not a Mapping.
        """
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError(
                "ConsensusAggregator: responses must be a non-empty mapping"
            )
        with Tapestry() as inner:
            if self._strategy == "majority_vote":
                ConsensusMajorityVotePicker(
                    responses=dict(responses),
                    _config=KnotConfig(id="consensus"),
                )
            else:
                ConsensusSynthesisCaller(
                    responses=dict(responses),
                    llm=self._llm,
                    _config=KnotConfig(id="consensus"),
                )
        inner_result = await self._run_inner(inner)
        consensus = inner_result.outputs.get("consensus")
        if not isinstance(consensus, AgentResponse):
            return self._fallback(responses)
        return consensus

    @staticmethod
    def _fallback(
        responses: Mapping[str, AgentResponse],
    ) -> AgentResponse:
        counter: Counter[str] = Counter(r.content for r in responses.values())
        if not counter:
            return AgentResponse(content="", finish_reason="stop")
        winning_content, _ = counter.most_common(1)[0]
        return AgentResponse(content=winning_content, finish_reason="stop")
