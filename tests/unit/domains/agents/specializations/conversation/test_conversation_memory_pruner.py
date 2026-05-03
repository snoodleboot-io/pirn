"""Tests for :class:`ConversationMemoryPruner`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.conversation.conversation_memory_pruner import (
    ConversationMemoryPruner,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_message(role: str, content: str) -> AgentMessage:
    return AgentMessage(role=role, content=content)


@pytest.mark.asyncio
class TestConversationMemoryPrunerConstruction:
    async def test_rejects_zero_token_budget(self) -> None:
        with pytest.raises(ValueError, match="token_budget must be a positive int"):
            with Tapestry():
                ConversationMemoryPruner(
                    messages=[],
                    token_budget=0,
                    _config=KnotConfig(id="cmp"),
                )


@pytest.mark.asyncio
class TestConversationMemoryPrunerProcess:
    async def test_returns_unchanged_when_within_budget(self) -> None:
        messages = [
            _make_message("user", "hi"),
            _make_message("assistant", "hello"),
        ]
        with Tapestry() as t:
            ConversationMemoryPruner(
                messages=messages,
                token_budget=1000,
                _config=KnotConfig(id="cmp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        pruned = result.outputs["cmp"]
        assert len(pruned) == 2

    async def test_prunes_oldest_non_system_messages(self) -> None:
        messages = [
            _make_message("system", "You are helpful."),
            _make_message("user", "a" * 50),
            _make_message("assistant", "b" * 50),
            _make_message("user", "c" * 50),
        ]
        with Tapestry() as t:
            ConversationMemoryPruner(
                messages=messages,
                token_budget=120,
                _config=KnotConfig(id="cmp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        pruned = result.outputs["cmp"]
        roles = [m.role for m in pruned]
        assert "system" in roles

    async def test_preserves_system_message(self) -> None:
        messages = [
            _make_message("system", "s" * 10),
            _make_message("user", "u" * 200),
        ]
        with Tapestry() as t:
            ConversationMemoryPruner(
                messages=messages,
                token_budget=15,
                _config=KnotConfig(id="cmp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        pruned = result.outputs["cmp"]
        assert len(pruned) == 1
        assert pruned[0].role == "system"

    async def test_rejects_non_agent_message_element(self) -> None:
        with pytest.raises(TypeError):
            with Tapestry():
                ConversationMemoryPruner(
                    messages=["not-a-message"],  # type: ignore[list-item]
                    token_budget=1000,
                    _config=KnotConfig(id="cmp"),
                )
