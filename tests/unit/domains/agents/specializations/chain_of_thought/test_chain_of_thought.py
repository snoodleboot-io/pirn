"""Unit tests for :class:`ChainOfThought`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.chain_of_thought.chain_of_thought import (
    ChainOfThought,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestChainOfThoughtProcess:
    async def test_returns_llm_content_as_agent_response(self) -> None:
        llm = StubLLMProvider(["Step 1: reason. Step 2: conclude. Final: 42."])
        with Tapestry() as t:
            ChainOfThought(
                prompt="What is the answer?",
                llm=llm,
                _config=KnotConfig(id="cot"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["cot"]
        assert isinstance(response, AgentResponse)
        assert response.content == "Step 1: reason. Step 2: conclude. Final: 42."

    async def test_passes_system_prompt_and_user_prompt_to_llm(self) -> None:
        llm = StubLLMProvider(["reasoning"])
        with Tapestry() as t:
            ChainOfThought(
                prompt="Explain gravity.",
                llm=llm,
                _config=KnotConfig(id="cot"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 1
        messages = llm.calls[0]
        assert messages[0]["role"] == "system"
        assert "step-by-step" in messages[0]["content"].lower()
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Explain gravity."


@pytest.mark.asyncio
class TestChainOfThoughtConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry():
                ChainOfThought(
                    prompt="q",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cot"),
                )

    async def test_rejects_non_string_prompt_at_construction(self) -> None:
        llm = StubLLMProvider(["x"])
        with pytest.raises(TypeError):
            with Tapestry():
                ChainOfThought(
                    prompt=42,  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="cot"),
                )
