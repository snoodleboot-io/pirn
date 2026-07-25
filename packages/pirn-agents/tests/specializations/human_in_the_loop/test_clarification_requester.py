"""Tests for :class:`ClarificationRequester`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.human_in_the_loop.clarification_requester import (
    ClarificationRequester,
)
from tests.specializations.conftest import StubLLMProvider


def _make_knot() -> ClarificationRequester:
    with Tapestry():
        return ClarificationRequester(
            message="hello",
            llm=StubLLMProvider(["CLEAR"]),
            _config=KnotConfig(id="cr"),
        )


class TestClarificationRequesterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_original_message_when_clear(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["CLEAR"])
        result = await k.process(message="What is the capital of France?", llm=llm)
        assert result == "What is the capital of France?"

    async def test_returns_clarifying_question_when_ambiguous(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["Could you clarify what you mean by 'it'?"])
        result = await k.process(message="Can you fix it?", llm=llm)
        assert result == "Could you clarify what you mean by 'it'?"

    async def test_rejects_non_string_message(self) -> None:
        k = _make_knot()
        llm = StubLLMProvider(["CLEAR"])
        with self.assertRaises(TypeError):
            await k.process(message=42, llm=llm)  # type: ignore[arg-type]
