"""Unit tests for :class:`DebateJudge`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.debate_judge import (
    DebateJudge,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


def _make_knot() -> DebateJudge:
    with Tapestry():
        return DebateJudge(
            topic="topic",
            final_round=[_resp("arg0")],
            judge_llm=StubLLMProvider(["0"]),
            _config=KnotConfig(id="dj"),
        )


class TestDebateJudgeProcess(unittest.IsolatedAsyncioTestCase):
    async def test_picks_response_by_index(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["1"])
        responses = [_resp("arg zero"), _resp("arg one")]
        out = await k.process(topic="The question", final_round=responses, judge_llm=llm)
        assert out.content == "arg one"

    async def test_falls_back_to_first_on_parse_failure(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["not-a-number"])
        responses = [_resp("first"), _resp("second")]
        out = await k.process(topic="topic", final_round=responses, judge_llm=llm)
        assert out.content == "first"

    async def test_rejects_empty_final_round(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["0"])
        with self.assertRaises(ValueError):
            await k.process(topic="topic", final_round=[], judge_llm=llm)

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(topic="t", final_round=[_resp("x")], judge_llm="bad")  # type: ignore[arg-type]

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["1"])
        responses = [_resp("arg zero"), _resp("arg one")]
        with Tapestry() as t:
            DebateJudge(
                topic="The question",
                final_round=responses,
                judge_llm=llm,
                _config=KnotConfig(id="dj"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["dj"].content == "arg one"
