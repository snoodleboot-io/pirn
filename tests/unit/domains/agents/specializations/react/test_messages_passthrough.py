"""Unit tests for :class:`MessagesPassthrough`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


class TestMessagesPassthroughProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_tuple_from_list(self) -> None:
        msgs = [
            AgentMessage(role="user", content="hello"),
            AgentMessage(role="assistant", content="hi"),
        ]
        with Tapestry() as t:
            MessagesPassthrough(
                messages=msgs,
                _config=KnotConfig(id="mp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mp"]
        assert isinstance(out, tuple)
        assert len(out) == 2

    async def test_returns_tuple_from_tuple(self) -> None:
        msgs = (AgentMessage(role="user", content="hey"),)
        with Tapestry() as t:
            MessagesPassthrough(
                messages=msgs,
                _config=KnotConfig(id="mp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mp"]
        assert isinstance(out, tuple)
        assert out[0].content == "hey"

    async def test_empty_returns_empty_tuple(self) -> None:
        with Tapestry() as t:
            MessagesPassthrough(
                messages=[],
                _config=KnotConfig(id="mp"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["mp"] == ()
