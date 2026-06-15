"""Tests for :class:`MultiTurnContextAssembler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.conversation.multi_turn_context_assembler import (
    MultiTurnContextAssembler,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_message(role: str, content: str) -> AgentMessage:
    return AgentMessage(role=role, content=content)


def _make_knot() -> MultiTurnContextAssembler:
    with Tapestry():
        return MultiTurnContextAssembler(
            messages=[],
            max_turns=10,
            max_tokens=1000,
            _config=KnotConfig(id="mtca"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_all_messages_within_limits(self) -> None:
        k = _make_knot()
        messages = [
            _make_message("user", "hello"),
            _make_message("assistant", "hi"),
        ]
        result = await k.process(messages=messages, max_turns=10, max_tokens=1000)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi"}

    async def test_respects_max_turns(self) -> None:
        k = _make_knot()
        messages = [_make_message("user", f"msg{i}") for i in range(5)]
        result = await k.process(messages=messages, max_turns=2, max_tokens=10000)
        assert len(result) == 2
        assert result[-1]["content"] == "msg4"

    async def test_respects_max_tokens(self) -> None:
        k = _make_knot()
        messages = [
            _make_message("user", "a" * 100),
            _make_message("assistant", "b" * 100),
            _make_message("user", "c" * 100),
        ]
        result = await k.process(messages=messages, max_turns=10, max_tokens=150)
        assert len(result) == 1
        assert result[0]["content"] == "c" * 100

    async def test_returns_empty_for_empty_messages(self) -> None:
        k = _make_knot()
        result = await k.process(messages=[], max_turns=5, max_tokens=1000)
        assert result == []

    async def test_rejects_zero_max_turns(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "max_turns must be a positive int"):
            await k.process(messages=[], max_turns=0, max_tokens=1000)

    async def test_rejects_zero_max_tokens(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "max_tokens must be a positive int"):
            await k.process(messages=[], max_turns=5, max_tokens=0)
