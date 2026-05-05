"""Tests for :class:`ConsensusAggregator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.consensus_aggregator import (
    ConsensusAggregator,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestConsensusAggregatorConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unsupported_strategy(self) -> None:
        llm = StubLLMProvider(["consensus-text"])
        with self.assertRaisesRegex(ValueError, "strategy"):
            with Tapestry():
                ConsensusAggregator(
                    responses={
                        "a": AgentResponse(content="x", finish_reason="stop"),
                    },
                    llm=llm,
                    strategy="quorum",
                    _config=KnotConfig(id="con"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                ConsensusAggregator(
                    responses={
                        "a": AgentResponse(content="x", finish_reason="stop"),
                    },
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="con"),
                )


class TestConsensusAggregatorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_majority_vote_returns_most_common_response(self) -> None:
        llm = StubLLMProvider(["unused-by-majority"])
        responses = {
            "a": AgentResponse(content="42", finish_reason="stop"),
            "b": AgentResponse(content="42", finish_reason="stop"),
            "c": AgentResponse(content="-1", finish_reason="stop"),
        }
        with Tapestry() as t:
            ConsensusAggregator(
                responses=responses,
                llm=llm,
                strategy="majority_vote",
                _config=KnotConfig(id="con"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        consensus = result.outputs["con"]
        assert isinstance(consensus, AgentResponse)
        assert consensus.content == "42"

    async def test_llm_synthesis_returns_synthesised_text(self) -> None:
        llm = StubLLMProvider(["the synthesis"])
        responses = {
            "a": AgentResponse(content="answer A", finish_reason="stop"),
            "b": AgentResponse(content="answer B", finish_reason="stop"),
        }
        with Tapestry() as t:
            ConsensusAggregator(
                responses=responses,
                llm=llm,
                strategy="llm_synthesis",
                _config=KnotConfig(id="con"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        consensus = result.outputs["con"]
        assert isinstance(consensus, AgentResponse)
        assert consensus.content == "the synthesis"
