"""Unit tests for :class:`SelfCritiqueRevise`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.reflection.self_critique_revise import (
    SelfCritiqueRevise,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestSelfCritiqueReviseProcess:
    async def test_returns_revised_answer_as_agent_response(self) -> None:
        llm = StubLLMProvider(["initial answer", "it lacks detail", "revised answer"])
        with Tapestry() as t:
            SelfCritiqueRevise(
                prompt="Explain ML.",
                llm=llm,
                _config=KnotConfig(id="scr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["scr"]
        assert isinstance(response, AgentResponse)
        assert response.content == "revised answer"

    async def test_makes_three_llm_calls(self) -> None:
        llm = StubLLMProvider(["gen", "crit", "rev"])
        with Tapestry() as t:
            SelfCritiqueRevise(
                prompt="q",
                llm=llm,
                _config=KnotConfig(id="scr"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 3

    async def test_revision_call_contains_critique(self) -> None:
        llm = StubLLMProvider(["initial", "the_critique_text", "final"])
        with Tapestry() as t:
            SelfCritiqueRevise(
                prompt="what is x?",
                llm=llm,
                _config=KnotConfig(id="scr"),
            )
        await t.run(RunRequest())
        revision_messages = llm.calls[2]
        user_content = revision_messages[-1]["content"]
        assert "the_critique_text" in user_content
        assert "initial" in user_content
        assert "what is x?" in user_content


@pytest.mark.asyncio
class TestSelfCritiqueReviseConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry():
                SelfCritiqueRevise(
                    prompt="q",
                    llm="not-llm",  # type: ignore[arg-type]
                    _config=KnotConfig(id="scr"),
                )
