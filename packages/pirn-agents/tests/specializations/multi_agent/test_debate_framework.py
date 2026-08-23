"""Tests for :class:`DebateFramework`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.debate_framework import (
    DebateFramework,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, response_sink

_DEBATER_REGISTRY: dict[str, str] = {}


class StubDebater(SubTapestry):
    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> Knot:
        argument = _DEBATER_REGISTRY.get(self.config.id, "argument")
        return response_sink(
            AgentResponse(content=argument, finish_reason="stop"),
            f"{self.config.id}_argument",
        )


class FailingDebater(SubTapestry):
    """A debater whose inner run raises — used to exercise the failure path."""

    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Knot:
        raise RuntimeError("debater boom")


def _make_knot(debaters: tuple, judge: StubLLMProvider) -> DebateFramework:
    with Tapestry():
        return DebateFramework(
            topic="t",
            debaters=debaters,
            judge_llm=judge,
            rounds=1,
            _config=KnotConfig(id="debate"),
        )


class TestDebateFrameworkProcess(unittest.IsolatedAsyncioTestCase):
    async def test_judge_picks_winning_debater(self) -> None:
        judge = StubLLMProvider(["1"])
        _DEBATER_REGISTRY["pro"] = "for the motion"
        _DEBATER_REGISTRY["con"] = "against the motion"
        with Tapestry():
            pro = StubDebater(_config=KnotConfig(id="pro"))
            con = StubDebater(_config=KnotConfig(id="con"))
        with Tapestry() as t:
            DebateFramework(
                topic="should we ship",
                debaters=(pro, con),
                judge_llm=judge,
                rounds=2,
                _config=KnotConfig(id="debate"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        winner = run.outputs["debate"]
        assert isinstance(winner, AgentResponse)
        assert winner.content == "against the motion"

    async def test_rejects_too_few_debaters(self) -> None:
        judge = StubLLMProvider(["0"])
        with Tapestry():
            only = StubDebater(_config=KnotConfig(id="solo"))
        k = _make_knot((only, only), judge)
        with self.assertRaises(ValueError):
            await k.process(topic="t", debaters=(only,), judge_llm=judge, rounds=1)

    async def test_rejects_non_positive_rounds(self) -> None:
        judge = StubLLMProvider(["0"])
        with Tapestry():
            a = StubDebater(_config=KnotConfig(id="a"))
            b = StubDebater(_config=KnotConfig(id="b"))
        k = _make_knot((a, b), judge)
        with self.assertRaises(ValueError):
            await k.process(topic="t", debaters=(a, b), judge_llm=judge, rounds=0)

    async def test_tapestry_run_integration(self) -> None:
        judge = StubLLMProvider(["1"])
        _DEBATER_REGISTRY["pro"] = "for the motion"
        _DEBATER_REGISTRY["con"] = "against the motion"
        with Tapestry():
            pro = StubDebater(_config=KnotConfig(id="pro"))
            con = StubDebater(_config=KnotConfig(id="con"))
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

    async def test_failure_mode_unchanged_when_a_debater_fails(self) -> None:
        # Unrolling the rounds into Aggregators gains NO per-debater isolation:
        # SubTapestry raises SubTapestryError on ANY inner failure, so one failing
        # debater fails the whole knot — byte-identical to the old per-round gather.
        judge = StubLLMProvider(["0"])
        _DEBATER_REGISTRY["sound"] = "sound argument"
        with Tapestry():
            good = StubDebater(_config=KnotConfig(id="sound"))
            bad = FailingDebater(_config=KnotConfig(id="bad"))
        with Tapestry() as t:
            DebateFramework(
                topic="should we ship",
                debaters=(good, bad),
                judge_llm=judge,
                rounds=2,
                _config=KnotConfig(id="debate"),
            )
        run = await t.run(RunRequest())
        assert not run.succeeded
        assert "debate" not in run.outputs
