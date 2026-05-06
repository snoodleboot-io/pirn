"""Unit tests for :class:`MessagesPassthrough`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


class TestMessagesPassthroughProcess(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MessagesPassthrough:
        with Tapestry():
            return MessagesPassthrough(
                messages=[],
                _config=KnotConfig(id="mp"),
            )

    async def test_returns_tuple_from_list(self) -> None:
        knot = self._make()
        msgs = [
            AgentMessage(role="user", content="hello"),
            AgentMessage(role="assistant", content="hi"),
        ]
        result = await knot.process(messages=msgs)
        assert isinstance(result, tuple)
        assert len(result) == 2

    async def test_returns_tuple_from_tuple(self) -> None:
        knot = self._make()
        msgs = (AgentMessage(role="user", content="hey"),)
        result = await knot.process(messages=msgs)
        assert isinstance(result, tuple)
        assert result[0].content == "hey"

    async def test_empty_returns_empty_tuple(self) -> None:
        knot = self._make()
        result = await knot.process(messages=[])
        assert result == ()
