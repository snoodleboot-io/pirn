"""Unit tests for :class:`DebateJudge`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.debate_judge import (
    DebateJudge,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


class TestDebateJudgeConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                DebateJudge(
                    topic="Should X?",
                    final_round=[],
                    judge_llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="dj"),
                )


class TestDebateJudgeProcess(unittest.IsolatedAsyncioTestCase):
    async def test_picks_response_by_index(self) -> None:
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

    async def test_falls_back_to_first_on_parse_failure(self) -> None:
        llm = StubLLMProvider(["not-a-number"])
        responses = [_resp("first"), _resp("second")]
        with Tapestry() as t:
            DebateJudge(
                topic="topic",
                final_round=responses,
                judge_llm=llm,
                _config=KnotConfig(id="dj"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["dj"].content == "first"

    async def test_rejects_empty_final_round(self) -> None:
        llm = StubLLMProvider(["0"])
        with Tapestry() as t:
            DebateJudge(
                topic="topic",
                final_round=[],
                judge_llm=llm,
                _config=KnotConfig(id="dj"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
