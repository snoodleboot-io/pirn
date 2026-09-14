"""Unit tests for :class:`ReActResponseExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_response_extractor import (
    ReActResponseExtractor,
)
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse


class TestReActResponseExtractorProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ReActResponseExtractor:
        with Tapestry():
            # ReActResponseExtractor needs a real Knot parent — a minimal
            # constant-seed Parameter stands in for one.
            seed = Parameter(
                "seed_messages", tuple[AgentMessage, ...], default=(), _config=KnotConfig(id="seed")
            )
            return ReActResponseExtractor(messages=seed, _config=KnotConfig(id="rre"))

    async def test_extracts_final_answer(self) -> None:
        knot = self._make()
        msgs = [
            AgentMessage(role="assistant", content="Thought: let me check.\nFinal Answer: 42"),
        ]
        out = await knot.process(messages=msgs)
        assert isinstance(out, AgentResponse)
        assert out.data == "42"
        assert out.metadata.finish_reason == "stop"

    async def test_returns_length_when_no_final_answer(self) -> None:
        knot = self._make()
        msgs = [
            AgentMessage(role="assistant", content="Still thinking..."),
        ]
        out = await knot.process(messages=msgs)
        assert out.metadata.finish_reason == "length"
        assert out.data == "Still thinking..."

    async def test_empty_messages_returns_empty_content(self) -> None:
        knot = self._make()
        out = await knot.process(messages=[])
        assert out.data == ""
        assert out.metadata.finish_reason == "length"

    async def test_skips_non_assistant_messages(self) -> None:
        knot = self._make()
        msgs = [
            AgentMessage(role="user", content="question"),
            AgentMessage(role="tool", content="tool output"),
        ]
        out = await knot.process(messages=msgs)
        assert out.data == ""
        assert out.metadata.finish_reason == "length"
