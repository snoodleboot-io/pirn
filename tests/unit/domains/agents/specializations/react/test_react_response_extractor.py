"""Unit tests for :class:`ReActResponseExtractor`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.react_response_extractor import (
    ReActResponseExtractor,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _MsgsSource(Knot):
    def __init__(self, msgs, *, _config, **kwargs):
        self._msgs = msgs
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return tuple(self._msgs)


class TestReActResponseExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_final_answer(self) -> None:
        msgs = [
            AgentMessage(role="assistant", content="Thought: let me check.\nFinal Answer: 42"),
        ]
        with Tapestry() as t:
            src = _MsgsSource(msgs, _config=KnotConfig(id="src"))
            ReActResponseExtractor(messages=src, _config=KnotConfig(id="rre"))
        result = await t.run(RunRequest())
        out = result.outputs["rre"]
        assert isinstance(out, AgentResponse)
        assert out.content == "42"
        assert out.finish_reason == "stop"

    async def test_returns_length_when_no_final_answer(self) -> None:
        msgs = [
            AgentMessage(role="assistant", content="Still thinking..."),
        ]
        with Tapestry() as t:
            src = _MsgsSource(msgs, _config=KnotConfig(id="src"))
            ReActResponseExtractor(messages=src, _config=KnotConfig(id="rre"))
        result = await t.run(RunRequest())
        out = result.outputs["rre"]
        assert out.finish_reason == "length"
        assert out.content == "Still thinking..."

    async def test_empty_messages_returns_empty_content(self) -> None:
        with Tapestry() as t:
            src = _MsgsSource([], _config=KnotConfig(id="src"))
            ReActResponseExtractor(messages=src, _config=KnotConfig(id="rre"))
        result = await t.run(RunRequest())
        out = result.outputs["rre"]
        assert out.content == ""
        assert out.finish_reason == "length"
