"""Unit tests for :class:`ConsensusMajorityVotePicker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.multi_agent.consensus_majority_vote_picker import (
    ConsensusMajorityVotePicker,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


def _make_knot() -> ConsensusMajorityVotePicker:
    with Tapestry():
        return ConsensusMajorityVotePicker(
            responses={"a": _resp("x")},
            _config=KnotConfig(id="mvp"),
        )


class TestConsensusMajorityVotePickerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_picks_majority_content(self) -> None:
        k = _make_knot()
        responses = {
            "a": _resp("blue"),
            "b": _resp("blue"),
            "c": _resp("red"),
        }
        result = await k.process(responses=responses)
        assert result.content == "blue"

    async def test_tie_broken_by_first_seen(self) -> None:
        k = _make_knot()
        responses = {"a": _resp("blue"), "b": _resp("red")}
        result = await k.process(responses=responses)
        assert result.content == "blue"

    async def test_rejects_empty_responses(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await k.process(responses={})

    async def test_rejects_non_agent_response_value(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(responses={"a": "not-a-response"})  # type: ignore[dict-item]

    async def test_single_response_returns_that_response(self) -> None:
        k = _make_knot()
        result = await k.process(responses={"only": _resp("sole")})
        assert result.content == "sole"
