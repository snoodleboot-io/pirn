"""Unit tests for :class:`ConversationBuffer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.memory.conversation_buffer import ConversationBuffer
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_knot() -> ConversationBuffer:
    @knot
    async def _m() -> AgentMessage:
        return AgentMessage(role="user", content="x")

    with Tapestry():
        upstream = _m(_config=KnotConfig(id="n"))
        return ConversationBuffer(
            new_message=upstream,
            max_size=50,
            _config=KnotConfig(id="cb"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_with_unbounded_history(self) -> None:
        k = _make_knot()
        history = (
            AgentMessage(role="user", content="a"),
            AgentMessage(role="assistant", content="b"),
        )
        out = await k.process(
            new_message=AgentMessage(role="user", content="latest"),
            history=history,
            max_size=10,
        )
        assert len(out) == 3
        assert out[-1].content == "latest"

    async def test_trims_to_max_size(self) -> None:
        k = _make_knot()
        history = tuple(AgentMessage(role="user", content=f"m{i}") for i in range(5))
        out = await k.process(
            new_message=AgentMessage(role="user", content="latest"),
            history=history,
            max_size=3,
        )
        assert len(out) == 3
        assert out[-1].content == "latest"
        assert out[0].content == "m3"

    async def test_rejects_non_positive_max_size(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await k.process(
                new_message=AgentMessage(role="user", content="x"),
                history=(),
                max_size=0,
            )

    async def test_rejects_non_agent_message(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                new_message="not a message",  # type: ignore[arg-type]
                history=(),
                max_size=10,
            )
