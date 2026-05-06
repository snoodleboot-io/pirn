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


def _make_knot() -> ConsensusAggregator:
    with Tapestry():
        return ConsensusAggregator(
            responses={"a": AgentResponse(content="x", finish_reason="stop")},
            llm=StubLLMProvider(["y"]),
            _config=KnotConfig(id="con"),
        )


class TestConsensusAggregatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_majority_vote_returns_most_common_response(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["unused-by-majority"])
        responses = {
            "a": AgentResponse(content="42", finish_reason="stop"),
            "b": AgentResponse(content="42", finish_reason="stop"),
            "c": AgentResponse(content="-1", finish_reason="stop"),
        }
        consensus = await k.process(responses=responses, llm=llm, strategy="majority_vote")
        assert isinstance(consensus, AgentResponse)
        assert consensus.content == "42"

    async def test_llm_synthesis_returns_synthesised_text(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["the synthesis"])
        responses = {
            "a": AgentResponse(content="answer A", finish_reason="stop"),
            "b": AgentResponse(content="answer B", finish_reason="stop"),
        }
        consensus = await k.process(responses=responses, llm=llm, strategy="llm_synthesis")
        assert isinstance(consensus, AgentResponse)
        assert consensus.content == "the synthesis"

    async def test_rejects_unsupported_strategy(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["x"])
        responses = {"a": AgentResponse(content="x", finish_reason="stop")}
        with self.assertRaises(ValueError):
            await k.process(responses=responses, llm=llm, strategy="quorum")

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        responses = {"a": AgentResponse(content="x", finish_reason="stop")}
        with self.assertRaises(TypeError):
            await k.process(responses=responses, llm="bad", strategy="majority_vote")  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
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
        assert result.outputs["con"].content == "the synthesis"
