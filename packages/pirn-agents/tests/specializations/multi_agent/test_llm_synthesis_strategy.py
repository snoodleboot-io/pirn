"""Unit tests for :class:`LlmSynthesisStrategy`."""

from __future__ import annotations

import unittest

from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.consensus_synthesis_caller import (
    ConsensusSynthesisCaller,
)
from pirn_agents.specializations.multi_agent.llm_synthesis_strategy import (
    LlmSynthesisStrategy,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestLlmSynthesisStrategy(unittest.TestCase):
    def test_name_is_llm_synthesis(self) -> None:
        assert LlmSynthesisStrategy().name() == "llm_synthesis"

    def test_build_returns_synthesis_caller(self) -> None:
        responses = {"a": AgentResponse(content="x", finish_reason="stop")}
        with Tapestry():
            knot = LlmSynthesisStrategy().build(
                responses=responses, llm=StubLLMProvider(["the synthesis"])
            )

        assert isinstance(knot, ConsensusSynthesisCaller)


if __name__ == "__main__":
    unittest.main()
