"""Unit tests for :class:`ConversationBuffer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory.conversation_buffer import ConversationBuffer
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


@knot
async def emit_new_message() -> AgentMessage:
    return AgentMessage(role="user", content="latest")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_with_unbounded_history(self) -> None:
        history = (
            AgentMessage(role="user", content="a"),
            AgentMessage(role="assistant", content="b"),
        )
        with Tapestry() as t:
            new_msg = emit_new_message(_config=KnotConfig(id="n"))
            ConversationBuffer(
                new_message=new_msg,
                history=history,
                max_size=10,
                _config=KnotConfig(id="cb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cb"]
        assert len(out) == 3
        assert out[-1].content == "latest"

    async def test_trims_to_max_size(self) -> None:
        history = tuple(
            AgentMessage(role="user", content=f"m{i}") for i in range(5)
        )
        with Tapestry() as t:
            new_msg = emit_new_message(_config=KnotConfig(id="n"))
            ConversationBuffer(
                new_message=new_msg,
                history=history,
                max_size=3,
                _config=KnotConfig(id="cb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cb"]
        assert len(out) == 3
        assert out[-1].content == "latest"
        assert out[0].content == "m3"


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_max_size(self) -> None:
        @knot
        async def m() -> AgentMessage:
            return AgentMessage(role="user", content="x")

        with Tapestry():
            new_msg = m(_config=KnotConfig(id="m"))
            with self.assertRaisesRegex(ValueError, "positive"):
                ConversationBuffer(
                    new_message=new_msg,
                    max_size=0,
                    _config=KnotConfig(id="cb"),
                )
