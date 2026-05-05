"""Unit tests for :class:`ConsensusSynthesisCaller`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.consensus_synthesis_caller import (
    ConsensusSynthesisCaller,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestConsensusSynthesisCallerConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                ConsensusSynthesisCaller(
                    responses={},
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="csc"),
                )


class TestConsensusSynthesisCallerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_synthesised_agent_response(self) -> None:
        llm = StubLLMProvider(["consensus answer"])
        responses = {
            "expert_a": AgentResponse(content="answer A", finish_reason="stop"),
            "expert_b": AgentResponse(content="answer B", finish_reason="stop"),
        }
        with Tapestry() as t:
            ConsensusSynthesisCaller(
                responses=responses,
                llm=llm,
                _config=KnotConfig(id="csc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["csc"]
        assert isinstance(out, AgentResponse)
        assert out.content == "consensus answer"

    async def test_rejects_empty_responses(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry() as t:
            ConsensusSynthesisCaller(
                responses={},
                llm=llm,
                _config=KnotConfig(id="csc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_all_responses_included_in_prompt(self) -> None:
        llm = StubLLMProvider(["synthesised"])
        responses = {
            "a": AgentResponse(content="resp-a", finish_reason="stop"),
            "b": AgentResponse(content="resp-b", finish_reason="stop"),
        }
        with Tapestry() as t:
            ConsensusSynthesisCaller(
                responses=responses,
                llm=llm,
                _config=KnotConfig(id="csc"),
            )
        await t.run(RunRequest())
        prompt_text = llm.calls[0][-1]["content"]
        assert "resp-a" in prompt_text
        assert "resp-b" in prompt_text
