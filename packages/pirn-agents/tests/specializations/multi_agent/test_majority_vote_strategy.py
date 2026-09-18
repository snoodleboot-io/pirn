"""Unit tests for :class:`MajorityVoteStrategy`."""

from __future__ import annotations

import unittest

from pirn.nodes.reduce_ import Reduce
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.majority_vote_strategy import (
    MajorityVoteStrategy,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestMajorityVoteStrategy(unittest.TestCase):
    def test_name_is_majority_vote(self) -> None:
        assert MajorityVoteStrategy().name() == "majority_vote"

    def test_build_returns_a_reduce_over_the_responses(self) -> None:
        responses = {"a": AgentResponse(content="x", finish_reason="stop")}
        with Tapestry():
            knot = MajorityVoteStrategy().build(
                responses=responses, llm=StubLLMProvider(["unused"])
            )

        assert isinstance(knot, Reduce)

    def test_combine_breaks_ties_by_first_seen_order(self) -> None:
        first = AgentResponse(content="tie", finish_reason="stop")
        second = AgentResponse(content="other", finish_reason="stop")
        third = AgentResponse(content="tie", finish_reason="stop")

        winner = MajorityVoteStrategy._combine([first, second, third])

        assert winner is first

    def test_combine_picks_the_most_common_content(self) -> None:
        a = AgentResponse(content="42", finish_reason="stop")
        b = AgentResponse(content="42", finish_reason="stop")
        c = AgentResponse(content="-1", finish_reason="stop")

        winner = MajorityVoteStrategy._combine([a, b, c])

        assert winner.data == "42"

    def test_combine_rejects_non_agent_response_items(self) -> None:
        with self.assertRaises(TypeError):
            MajorityVoteStrategy._combine(["not-a-response"])


if __name__ == "__main__":
    unittest.main()
