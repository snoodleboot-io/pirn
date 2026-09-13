"""Unit tests for :class:`MessagesPassthrough`."""

from __future__ import annotations

import unittest
import warnings

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn_agents.types.messaging.agent_message import AgentMessage


class _UpstreamMessages(Knot):
    async def process(self, **_: object) -> tuple[AgentMessage, ...]:
        return ()


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


class TestMessagesPassthroughDeprecationNotice(unittest.TestCase):
    """ADR agents-speaks-core WS5b: warns only for the constant-seed idiom."""

    def test_constant_seed_warns(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            MessagesPassthrough(messages=[], _config=KnotConfig(id="mp"))
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)
        assert "MessagesPassthrough" in str(caught[0].message)

    def test_upstream_knot_does_not_warn(self) -> None:
        with Tapestry():
            upstream = _UpstreamMessages(_config=KnotConfig(id="upstream"))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                MessagesPassthrough(messages=upstream, _config=KnotConfig(id="mp"))
        assert len(caught) == 0
