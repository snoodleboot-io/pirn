"""Tests for :class:`ConsensusAggregator` — deprecation shim for :class:`ConsensusPipeline`.

ADR agents-speaks-core WS5b. Behavioral coverage lives in
``test_consensus_pipeline.py``; this file pins only the shim's two extra
obligations: it still works, and it warns.
"""

from __future__ import annotations

import unittest
import warnings

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.consensus_aggregator import (
    ConsensusAggregator,
)
from pirn_agents.specializations.multi_agent.consensus_pipeline import ConsensusPipeline
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestConsensusAggregatorIsConsensusPipeline(unittest.TestCase):
    def test_is_a_subclass(self) -> None:
        assert issubclass(ConsensusAggregator, ConsensusPipeline)


class TestConsensusAggregatorStillWorks(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_to_consensus_pipeline_behaviour(self) -> None:
        llm = StubLLMProvider(["the synthesis"])
        responses = {"a": AgentResponse(content="answer A", finish_reason="stop")}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
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


class TestConsensusAggregatorWarnsOnConstruction(unittest.TestCase):
    def test_construction_warns(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ConsensusAggregator(
                responses={"a": AgentResponse(content="x", finish_reason="stop")},
                llm=StubLLMProvider(["y"]),
                _config=KnotConfig(id="con"),
            )
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)
        assert "ConsensusAggregator" in str(caught[0].message)
