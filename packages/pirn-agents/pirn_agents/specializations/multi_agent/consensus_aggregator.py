"""``ConsensusAggregator`` — fuse multiple :class:`AgentResponse`s.

A :class:`SubTapestry` that takes a mapping of specialist responses
and produces a single consensus :class:`AgentResponse`. Two
strategies are supported:

* ``"majority_vote"`` — group responses by their ``content`` and
  return the most common one. Ties are broken by first-seen order.
* ``"llm_synthesis"`` — feed every response into an LLM and return its
  synthesised reply.

Algorithm:
    1. Validate ``strategy`` against the supported set.
    2. Build an inner :class:`Tapestry` containing either
       :class:`ConsensusMajorityVotePicker` or
       :class:`ConsensusSynthesisCaller` depending on ``strategy``.
    3. Execute the inner tapestry via ``self._run_inner(inner)``.
    4. Return the knot output, falling back to majority vote on type mismatch.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent.consensus_strategy import ConsensusStrategy
from pirn_agents.specializations.multi_agent.llm_synthesis_strategy import (
    LlmSynthesisStrategy,
)
from pirn_agents.specializations.multi_agent.majority_vote_strategy import (
    MajorityVoteStrategy,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class ConsensusAggregator(AgentPipeline):
    """Reduces specialist responses to one :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        llm: Knot | LLMProvider,
        strategy: Knot | str = "llm_synthesis",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(responses=responses, llm=llm, strategy=strategy, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        llm: LLMProvider,
        strategy: str = "llm_synthesis",
        **_: Any,
    ) -> Any:
        """Apply the configured consensus strategy to the specialist responses and return the winner.

        Args:
            responses: A non-empty mapping of specialist names to their AgentResponse outputs.

        Returns:
            A single AgentResponse representing the consensus result.

        Raises:
            ValueError: If responses is empty or not a Mapping.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ConsensusAggregator: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        strategies = self._consensus_strategies()
        supported = tuple(candidate.name() for candidate in strategies)
        if strategy not in supported:
            raise ValueError(
                f"ConsensusAggregator: strategy must be one of {supported!r}, got {strategy!r}"
            )
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError("ConsensusAggregator: responses must be a non-empty mapping")
        for candidate in strategies:
            if candidate.matches(strategy):
                return candidate.build(responses=responses, llm=llm)
        # Unreachable — strategy was validated against the same tuple above.
        raise ValueError(f"ConsensusAggregator: no strategy matched {strategy!r}")

    @staticmethod
    def _consensus_strategies() -> tuple[ConsensusStrategy, ...]:
        """Return the ordered consensus mechanisms.

        A new mechanism is a new :class:`ConsensusStrategy` subclass appended
        here — the dispatch loop in :meth:`process` never changes (OCP).
        """
        return (MajorityVoteStrategy(), LlmSynthesisStrategy())

    @staticmethod
    def _fallback(
        responses: Mapping[str, AgentResponse],
    ) -> AgentResponse:
        counter: Counter[str] = Counter(r.content for r in responses.values())
        if not counter:
            return AgentResponse(content="", finish_reason="stop")
        winning_content, _ = counter.most_common(1)[0]
        return AgentResponse(content=winning_content, finish_reason="stop")
