"""``LlmSynthesisStrategy`` — the ``llm_synthesis`` consensus mechanism.

Builds a
:class:`pirn_agents.specializations.multi_agent.consensus_synthesis_caller.ConsensusSynthesisCaller`
inner stage, which feeds every specialist response to the LLM and returns its
synthesised reply.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.multi_agent.consensus_strategy import ConsensusStrategy
from pirn_agents.specializations.multi_agent.consensus_synthesis_caller import (
    ConsensusSynthesisCaller,
)
from pirn_agents.types.agent_response import AgentResponse


class LlmSynthesisStrategy(ConsensusStrategy):
    """Reduce responses by asking an LLM to synthesise a consensus reply."""

    def name(self) -> str:
        """Return the ``llm_synthesis`` selector name."""
        return "llm_synthesis"

    def build(
        self,
        *,
        responses: Mapping[str, AgentResponse],
        llm: LLMProvider,
    ) -> Knot:
        """Build a :class:`ConsensusSynthesisCaller` over ``responses``."""
        return ConsensusSynthesisCaller(
            responses=dict(responses),
            llm=llm,
            _config=KnotConfig(id="consensus"),
        )
