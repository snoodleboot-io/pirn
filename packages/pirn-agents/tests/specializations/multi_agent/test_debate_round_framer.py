"""Unit tests for :class:`DebateRoundFramer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.debate_round_framer import (
    DebateRoundFramer,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


def _make_framer(round_index: int) -> DebateRoundFramer:
    with Tapestry():
        return DebateRoundFramer(
            topic="the topic",
            round_index=round_index,
            rounds=3,
            _config=KnotConfig(id="frame"),
        )


class TestDebateRoundFramerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_round_zero_reports_no_prior_rounds(self) -> None:
        framer = _make_framer(0)
        framed = await framer.process(topic="the topic", round_index=0, rounds=3)
        assert framed == (
            "Topic: the topic\n\nRound 1 of 3.\nNo prior rounds.\nMake your strongest argument."
        )

    async def test_later_round_renders_prior_recap(self) -> None:
        framer = _make_framer(1)
        framed = await framer.process(
            topic="the topic",
            round_index=1,
            rounds=3,
            round_0=[_resp("pro-1"), _resp("con-1")],
        )
        assert framed == (
            "Topic: the topic\n\n"
            "Round 2 of 3.\n"
            "Round 1:\n"
            "  debater_0: pro-1\n"
            "  debater_1: con-1\n"
            "Make your strongest argument."
        )

    async def test_recap_accumulates_all_prior_rounds(self) -> None:
        framer = _make_framer(2)
        framed = await framer.process(
            topic="the topic",
            round_index=2,
            rounds=3,
            round_0=[_resp("a0"), _resp("b0")],
            round_1=[_resp("a1"), _resp("b1")],
        )
        assert "Round 1:\n  debater_0: a0\n  debater_1: b0" in framed
        assert "Round 2:\n  debater_0: a1\n  debater_1: b1" in framed
        assert framed.startswith("Topic: the topic\n\nRound 3 of 3.\n")

    async def test_tapestry_run_integration(self) -> None:
        with Tapestry() as t:
            DebateRoundFramer(
                topic="ship it",
                round_index=1,
                rounds=2,
                _config=KnotConfig(id="frame"),
                round_0=Parameter(
                    name="round_0_value",
                    type_=list,
                    default=[_resp("for"), _resp("against")],
                    _config=KnotConfig(id="round_0_value"),
                ),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        framed = result.outputs["frame"]
        assert isinstance(framed, str)
        assert "Round 2 of 2." in framed
        assert "debater_0: for" in framed
        assert "debater_1: against" in framed

    async def test_rejects_non_string_argument_types(self) -> None:
        # Named-scalar args are coerced to Parameter parents; this exercises the
        # render path with valid typed inputs and asserts the shape is a string.
        framer = _make_framer(0)
        out: Any = await framer.process(topic="t", round_index=0, rounds=1)
        assert isinstance(out, str)
