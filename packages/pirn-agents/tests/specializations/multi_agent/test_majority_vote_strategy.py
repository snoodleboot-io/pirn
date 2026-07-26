"""Unit tests for :class:`MajorityVoteStrategy`."""

from __future__ import annotations

import unittest

from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.consensus_majority_vote_picker import (
    ConsensusMajorityVotePicker,
)
from pirn_agents.specializations.multi_agent.majority_vote_strategy import (
    MajorityVoteStrategy,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestMajorityVoteStrategy(unittest.TestCase):
    def test_name_is_majority_vote(self) -> None:
        assert MajorityVoteStrategy().name() == "majority_vote"

    def test_build_returns_majority_vote_picker(self) -> None:
        responses = {"a": AgentResponse(content="x", finish_reason="stop")}
        with Tapestry():
            knot = MajorityVoteStrategy().build(
                responses=responses, llm=StubLLMProvider(["unused"])
            )

        assert isinstance(knot, ConsensusMajorityVotePicker)


if __name__ == "__main__":
    unittest.main()
