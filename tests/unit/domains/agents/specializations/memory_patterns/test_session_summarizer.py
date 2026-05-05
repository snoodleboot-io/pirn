"""Tests for :class:`SessionSummarizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


class TestSessionSummarizerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                SessionSummarizer(
                    messages=(),
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="summ"),
                )

    async def test_rejects_zero_token_threshold(self) -> None:
        llm = StubLLMProvider(["summary"])
        with self.assertRaisesRegex(ValueError, "token_threshold must be a positive int"):
            with Tapestry():
                SessionSummarizer(
                    messages=(),
                    llm=llm,
                    token_threshold=0,
                    _config=KnotConfig(id="summ"),
                )


class TestSessionSummarizerBelowThreshold(unittest.IsolatedAsyncioTestCase):
    async def test_returns_messages_unchanged_when_under_threshold(self) -> None:
        messages = make_messages(2, words_each=5)
        llm = StubLLMProvider(["summary"])
        with Tapestry() as t:
            SessionSummarizer(
                messages=messages,
                llm=llm,
                token_threshold=1000,
                _config=KnotConfig(id="summ"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["summ"]
        assert output == messages
        assert llm.calls == []


class TestSessionSummarizerAboveThreshold(unittest.IsolatedAsyncioTestCase):
    async def test_compresses_long_history(self) -> None:
        messages = make_messages(20, words_each=10)
        llm = StubLLMProvider(["Condensed summary of the conversation."])
        with Tapestry() as t:
            SessionSummarizer(
                messages=messages,
                llm=llm,
                token_threshold=50,
                _config=KnotConfig(id="summ"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["summ"]
        assert len(output) == 2
        assert output[0].role == "system"
        assert "[Summary]" in output[0].content
        assert "Condensed summary" in output[0].content
        assert output[1] == messages[-1]
        assert len(llm.calls) == 1

    async def test_summary_message_retains_last_user_message(self) -> None:
        messages = [
            AgentMessage(role="user", content="word " * 100),
            AgentMessage(role="assistant", content="word " * 100),
            AgentMessage(role="user", content="final question"),
        ]
        llm = StubLLMProvider(["Brief summary."])
        with Tapestry() as t:
            SessionSummarizer(
                messages=messages,
                llm=llm,
                token_threshold=10,
                _config=KnotConfig(id="summ"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["summ"]
        assert output[-1].content == "final question"
