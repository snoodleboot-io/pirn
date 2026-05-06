"""Tests for :class:`SessionSummarizer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.memory_patterns.session_summarizer import (
    SessionSummarizer,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def make_messages(count: int, words_each: int = 10) -> list[AgentMessage]:
    return [
        AgentMessage(
            role="user" if i % 2 == 0 else "assistant",
            content=(" ".join(["word"] * words_each)),
        )
        for i in range(count)
    ]


def _make_knot() -> SessionSummarizer:
    with Tapestry():
        return SessionSummarizer(
            messages=(),
            llm=StubLLMProvider(["summary"]),
            _config=KnotConfig(id="summ"),
        )


class TestSessionSummarizerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_messages_unchanged_when_under_threshold(self) -> None:
        k = _make_knot()
        messages = make_messages(2, words_each=5)
        llm = StubLLMProvider(["summary"])
        result = await k.process(messages=messages, llm=llm, token_threshold=1000)
        assert result == messages
        assert llm.calls == []

    async def test_compresses_long_history(self) -> None:
        k = _make_knot()
        messages = make_messages(20, words_each=10)
        llm = StubLLMProvider(["Condensed summary of the conversation."])
        result = await k.process(messages=messages, llm=llm, token_threshold=50)
        assert len(result) == 2
        assert result[0].role == "system"
        assert "[Summary]" in result[0].content
        assert "Condensed summary" in result[0].content
        assert result[1] == messages[-1]
        assert len(llm.calls) == 1

    async def test_summary_message_retains_last_user_message(self) -> None:
        k = _make_knot()
        messages = [
            AgentMessage(role="user", content="word " * 100),
            AgentMessage(role="assistant", content="word " * 100),
            AgentMessage(role="user", content="final question"),
        ]
        llm = StubLLMProvider(["Brief summary."])
        result = await k.process(messages=messages, llm=llm, token_threshold=10)
        assert result[-1].content == "final question"

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(messages=[], llm="bad", token_threshold=1000)  # type: ignore[arg-type]

    async def test_rejects_zero_token_threshold(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["summary"])
        with self.assertRaises(ValueError):
            await k.process(messages=[], llm=llm, token_threshold=0)
