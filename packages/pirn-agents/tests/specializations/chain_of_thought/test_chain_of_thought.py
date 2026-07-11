"""Unit tests for :class:`ChainOfThought`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.chain_of_thought.chain_of_thought import (
    ChainOfThought,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> ChainOfThought:
    with Tapestry():
        return ChainOfThought(
            prompt="x",
            llm=llm,
            _config=KnotConfig(id="cot"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_llm_content_as_agent_response(self) -> None:
        llm = StubLLMProvider(["Step 1: reason. Step 2: conclude. Final: 42."])
        k = _make_knot(llm)
        response = await k.process(prompt="What is the answer?", llm=llm)
        assert isinstance(response, AgentResponse)
        assert response.content == "Step 1: reason. Step 2: conclude. Final: 42."

    async def test_passes_system_prompt_and_user_prompt_to_llm(self) -> None:
        llm = StubLLMProvider(["reasoning"])
        k = _make_knot(llm)
        await k.process(prompt="Explain gravity.", llm=llm)
        assert len(llm.calls) == 1
        messages = llm.calls[0]
        assert messages[0]["role"] == "system"
        assert "step-by-step" in messages[0]["content"].lower()
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Explain gravity."

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                prompt="q",
                llm="not-a-provider",  # type: ignore[arg-type]
            )

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(
                prompt=42,  # type: ignore[arg-type]
                llm=llm,
            )
