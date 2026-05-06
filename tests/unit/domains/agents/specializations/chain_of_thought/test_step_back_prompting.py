"""Unit tests for :class:`StepBackPrompting`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.chain_of_thought.step_back_prompting import (
    StepBackPrompting,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> StepBackPrompting:
    with Tapestry():
        return StepBackPrompting(
            prompt="x",
            llm=llm,
            _config=KnotConfig(id="sbp"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_forward_answer_as_response(self) -> None:
        llm = StubLLMProvider(["principles about physics", "gravity pulls objects"])
        k = _make_knot(llm)
        response = await k.process(prompt="Why do apples fall?", llm=llm)
        assert isinstance(response, AgentResponse)
        assert response.content == "gravity pulls objects"

    async def test_makes_two_llm_calls(self) -> None:
        llm = StubLLMProvider(["background", "answer"])
        k = _make_knot(llm)
        await k.process(prompt="q", llm=llm)
        assert len(llm.calls) == 2

    async def test_forward_call_contains_step_back_answer(self) -> None:
        llm = StubLLMProvider(["principle_xyz", "final answer"])
        k = _make_knot(llm)
        await k.process(prompt="original question", llm=llm)
        forward_messages = llm.calls[1]
        assert any("principle_xyz" in m["content"] for m in forward_messages)
        assert any("original question" in m["content"] for m in forward_messages)

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                prompt="q",
                llm=None,  # type: ignore[arg-type]
            )
