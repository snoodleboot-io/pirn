"""Tests for :class:`DebateFramework`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.debate_framework import (
    DebateFramework,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class StubDebater(SubTapestry):
    def __init__(
        self,
        *,
        task: Any = "",
        _config: KnotConfig,
        argument: str = "argument",
        **kwargs: Any,
    ) -> None:
        self._argument = argument
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        return AgentResponse(content=self._argument, finish_reason="stop")


@pytest.mark.asyncio
class TestDebateFrameworkConstruction:
    async def test_rejects_too_few_debaters(self) -> None:
        judge = StubLLMProvider(["0"])
        with Tapestry():
            only = StubDebater(_config=KnotConfig(id="solo"))
        with pytest.raises(ValueError, match="at least two debaters"):
            with Tapestry():
                DebateFramework(
                    topic="t",
                    debaters=(only,),
                    judge_llm=judge,
                    _config=KnotConfig(id="debate"),
                )

    async def test_rejects_non_positive_rounds(self) -> None:
        judge = StubLLMProvider(["0"])
        with Tapestry():
            a = StubDebater(_config=KnotConfig(id="a"))
            b = StubDebater(_config=KnotConfig(id="b"))
        with pytest.raises(ValueError, match="rounds"):
            with Tapestry():
                DebateFramework(
                    topic="t",
                    debaters=(a, b),
                    judge_llm=judge,
                    rounds=0,
                    _config=KnotConfig(id="debate"),
                )


@pytest.mark.asyncio
class TestDebateFrameworkHappyPath:
    async def test_judge_picks_winning_debater(self) -> None:
        judge = StubLLMProvider(["1"])
        with Tapestry():
            pro = StubDebater(
                _config=KnotConfig(id="pro"),
                argument="for the motion",
            )
            con = StubDebater(
                _config=KnotConfig(id="con"),
                argument="against the motion",
            )
        with Tapestry() as t:
            DebateFramework(
                topic="should we ship",
                debaters=(pro, con),
                judge_llm=judge,
                rounds=2,
                _config=KnotConfig(id="debate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        winner = result.outputs["debate"]
        assert isinstance(winner, AgentResponse)
        assert winner.content == "against the motion"
