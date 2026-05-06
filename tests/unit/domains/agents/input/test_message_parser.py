"""Unit tests for :class:`MessageParser`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.input.message_parser import MessageParser
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_knot() -> MessageParser:
    @knot
    async def _r() -> str:
        return "x"

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="raw"))
        return MessageParser(raw_input=upstream, _config=KnotConfig(id="p"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_string_becomes_user_message(self) -> None:
        k = _make_knot()
        out = await k.process(raw_input="hello world")
        assert isinstance(out, tuple) and len(out) == 1
        assert out[0].role == "user"
        assert out[0].content == "hello world"

    async def test_mapping_with_role(self) -> None:
        k = _make_knot()
        out = await k.process(raw_input={"role": "assistant", "content": "hi there"})
        assert out[0].role == "assistant"
        assert out[0].content == "hi there"

    async def test_sequence_of_mixed_items(self) -> None:
        k = _make_knot()
        out = await k.process(
            raw_input=(
                {"role": "user", "content": "u"},
                AgentMessage(role="assistant", content="a"),
                "plain string",
            )
        )
        assert len(out) == 3
        assert out[0].role == "user"
        assert out[1].role == "assistant"
        assert out[2].role == "user"
        assert out[2].content == "plain string"

    async def test_rejects_unknown_type(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(raw_input=42)  # type: ignore[arg-type]
