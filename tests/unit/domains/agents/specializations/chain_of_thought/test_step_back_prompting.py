"""Unit tests for :class:`StepBackPrompting`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.chain_of_thought.step_back_prompting import (
    StepBackPrompting,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestStepBackPromptingProcess:
    async def test_returns_forward_answer_as_response(self) -> None:
        llm = StubLLMProvider(["principles about physics", "gravity pulls objects"])
        with Tapestry() as t:
            StepBackPrompting(
                prompt="Why do apples fall?",
                llm=llm,
                _config=KnotConfig(id="sbp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["sbp"]
        assert isinstance(response, AgentResponse)
        assert response.content == "gravity pulls objects"

    async def test_makes_two_llm_calls(self) -> None:
        llm = StubLLMProvider(["background", "answer"])
        with Tapestry() as t:
            StepBackPrompting(
                prompt="q",
                llm=llm,
                _config=KnotConfig(id="sbp"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 2

    async def test_forward_call_contains_step_back_answer(self) -> None:
        llm = StubLLMProvider(["principle_xyz", "final answer"])
        with Tapestry() as t:
            StepBackPrompting(
                prompt="original question",
                llm=llm,
                _config=KnotConfig(id="sbp"),
            )
        await t.run(RunRequest())
        forward_messages = llm.calls[1]
        assert any("principle_xyz" in m["content"] for m in forward_messages)
        assert any("original question" in m["content"] for m in forward_messages)


@pytest.mark.asyncio
class TestStepBackPromptingConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry():
                StepBackPrompting(
                    prompt="q",
                    llm=None,  # type: ignore[arg-type]
                    _config=KnotConfig(id="sbp"),
                )
