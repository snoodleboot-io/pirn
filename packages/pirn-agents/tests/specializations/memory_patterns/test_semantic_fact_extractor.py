"""Unit tests for :class:`SemanticFactExtractor`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.unreadable_llm_response_error import (
    UnreadableLlmResponseError,
)
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.memory.patterns.semantic_fact_extractor import (
    SemanticFactExtractor,
)
from pirn_agents.types.messaging.agent_message import AgentMessage
from tests.specializations.conftest import StubLLMProvider


def _make_knot() -> SemanticFactExtractor:
    with Tapestry():
        return SemanticFactExtractor(
            messages=[],
            llm=StubLLMProvider([]),
            fact_extraction_prompt="Extract facts:",
            _config=KnotConfig(id="sfe"),
        )


class _UnreadableLLMProvider(LLMProvider):
    """A provider whose reply matches no chat-completion shape the codebase knows.

    Implements :class:`LLMProvider` directly rather than subclassing a stub, so
    it stays outside the ``BaseLLMProvider`` content-identity hierarchy.
    """

    def __init__(self) -> None:
        self.calls: list[list[Mapping[str, Any]]] = []

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        self.calls.append([dict(m) for m in messages])
        return {"choices": [{"message": {"content": "The sky is blue."}}]}

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        raise NotImplementedError("_UnreadableLLMProvider does not stream")


class TestSemanticFactExtractorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_list_of_facts(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["Water boils at 100C\nIce melts at 0C"])
        msgs = [AgentMessage(role="user", content="tell me about water")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract facts:")
        assert isinstance(facts, list)
        assert len(facts) == 2

    async def test_strips_bullet_markers(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["- fact one\n* fact two"])
        msgs = [AgentMessage(role="user", content="hi")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract:")
        assert all(not f.startswith(("-", "*")) for f in facts)

    async def test_empty_llm_reply_returns_empty_list(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider([""])
        msgs = [AgentMessage(role="user", content="hi")]
        facts = await k.process(messages=msgs, llm=llm, fact_extraction_prompt="Extract:")
        assert facts == []

    async def test_an_unreadable_reply_fails_instead_of_inventing_facts(self) -> None:
        """PIR-873: the repr of an unreadable reply was split into lines and stored as facts."""
        k = _make_knot()
        msgs = [AgentMessage(role="user", content="hi")]
        with self.assertRaises(UnreadableLlmResponseError):
            await k.process(
                messages=msgs,
                llm=_UnreadableLLMProvider(),
                fact_extraction_prompt="Extract:",
            )

    async def test_rejects_non_llm_provider(self) -> None:
        k = _make_knot()
        result = await k({"messages": [], "llm": "bad", "fact_extraction_prompt": "Extract:"})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_empty_fact_extraction_prompt(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider([])
        with self.assertRaises(ValueError):
            await k.process(messages=[], llm=llm, fact_extraction_prompt="")
