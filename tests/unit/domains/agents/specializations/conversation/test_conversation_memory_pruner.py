"""Tests for :class:`ConversationMemoryPruner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.conversation.conversation_memory_pruner import (
    ConversationMemoryPruner,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_message(role: str, content: str) -> AgentMessage:
    return AgentMessage(role=role, content=content)


def _make_knot() -> ConversationMemoryPruner:
    with Tapestry():
        return ConversationMemoryPruner(
            messages=[],
            token_budget=1000,
            _config=KnotConfig(id="cmp"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_unchanged_when_within_budget(self) -> None:
        k = _make_knot()
        messages = [
            _make_message("user", "hi"),
            _make_message("assistant", "hello"),
        ]
        result = await k.process(messages=messages, token_budget=1000)
        assert len(result) == 2

    async def test_prunes_oldest_non_system_messages(self) -> None:
        k = _make_knot()
        messages = [
            _make_message("system", "You are helpful."),
            _make_message("user", "a" * 50),
            _make_message("assistant", "b" * 50),
            _make_message("user", "c" * 50),
        ]
        result = await k.process(messages=messages, token_budget=120)
        roles = [m.role for m in result]
        assert "system" in roles

    async def test_preserves_system_message(self) -> None:
        k = _make_knot()
        messages = [
            _make_message("system", "s" * 10),
            _make_message("user", "u" * 200),
        ]
        result = await k.process(messages=messages, token_budget=15)
        assert len(result) == 1
        assert result[0].role == "system"

    async def test_rejects_zero_token_budget(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "token_budget must be a positive int"):
            await k.process(messages=[], token_budget=0)

    async def test_rejects_non_agent_message_element(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(messages=["not-a-message"], token_budget=1000)  # type: ignore[list-item]
