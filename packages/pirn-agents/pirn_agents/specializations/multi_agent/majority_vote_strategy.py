"""``MajorityVoteStrategy`` — the ``majority_vote`` consensus mechanism.

Builds a
:class:`pirn_agents.specializations.multi_agent.consensus_majority_vote_picker.ConsensusMajorityVotePicker`
inner stage, which groups responses by ``content`` and returns the most common
one (ties broken by first-seen order). It needs no LLM.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.multi_agent.consensus_majority_vote_picker import (
    ConsensusMajorityVotePicker,
)
from pirn_agents.specializations.multi_agent.consensus_strategy import ConsensusStrategy
from pirn_agents.types.agent_response import AgentResponse


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
        """Build a :class:`ConsensusMajorityVotePicker` over ``responses``."""
        return ConsensusMajorityVotePicker(
            responses=dict(responses),
            _config=KnotConfig(id="consensus"),
        )
