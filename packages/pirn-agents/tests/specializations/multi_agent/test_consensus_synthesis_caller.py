"""Unit tests for :class:`ConsensusSynthesisCaller`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.consensus_synthesis_caller import (
    ConsensusSynthesisCaller,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _make_knot() -> ConsensusSynthesisCaller:
    with Tapestry():
        return ConsensusSynthesisCaller(
            responses={},
            llm=StubLLMProvider(["x"]),
            _config=KnotConfig(id="csc"),
        )


class TestConsensusSynthesisCallerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_synthesised_agent_response(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["consensus answer"])
        responses = {
            "expert_a": AgentResponse(content="answer A", finish_reason="stop"),
            "expert_b": AgentResponse(content="answer B", finish_reason="stop"),
        }
        out = await k.process(responses=responses, llm=llm)
        assert isinstance(out, AgentResponse)
        assert out.content == "consensus answer"

    async def test_rejects_empty_responses(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["x"])
        with self.assertRaises(ValueError):
            await k.process(responses={}, llm=llm)

    async def test_all_responses_included_in_prompt(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["synthesised"])
        responses = {
            "a": AgentResponse(content="resp-a", finish_reason="stop"),
            "b": AgentResponse(content="resp-b", finish_reason="stop"),
        }
        await k.process(responses=responses, llm=llm)
        prompt_text = llm.calls[0][-1]["content"]
        assert "resp-a" in prompt_text
        assert "resp-b" in prompt_text

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                responses={"a": AgentResponse(content="x", finish_reason="stop")}, llm="bad"
            )  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["the synthesis"])
        responses = {
            "a": AgentResponse(content="answer A", finish_reason="stop"),
            "b": AgentResponse(content="answer B", finish_reason="stop"),
        }
        with Tapestry() as t:
            ConsensusSynthesisCaller(
                responses=responses,
                llm=llm,
                _config=KnotConfig(id="csc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["csc"].content == "the synthesis"
