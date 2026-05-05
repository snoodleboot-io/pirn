"""Unit tests for :class:`ConsensusMajorityVotePicker`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.consensus_majority_vote_picker import (
    ConsensusMajorityVotePicker,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _resp(content: str) -> AgentResponse:
    return AgentResponse(content=content, finish_reason="stop")


class TestConsensusMajorityVotePickerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_picks_majority_content(self) -> None:
        responses = {
            "a": _resp("blue"),
            "b": _resp("blue"),
            "c": _resp("red"),
        }
        with Tapestry() as t:
            ConsensusMajorityVotePicker(
                responses=responses,
                _config=KnotConfig(id="mvp"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mvp"].content == "blue"

    async def test_tie_broken_by_first_seen(self) -> None:
        responses = {"a": _resp("blue"), "b": _resp("red")}
        with Tapestry() as t:
            ConsensusMajorityVotePicker(
                responses=responses,
                _config=KnotConfig(id="mvp"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mvp"].content == "blue"

    async def test_rejects_empty_responses(self) -> None:
        with Tapestry() as t:
            ConsensusMajorityVotePicker(
                responses={},
                _config=KnotConfig(id="mvp"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_agent_response_value(self) -> None:
        with Tapestry():
            with self.assertRaises(TypeError):
                ConsensusMajorityVotePicker(
                    responses={"a": "not-a-response"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="mvp"),
                )
