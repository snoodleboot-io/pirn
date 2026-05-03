"""Tests for :class:`ClarificationRequester`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.human_in_the_loop.clarification_requester import (
    ClarificationRequester,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestClarificationRequesterConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                ClarificationRequester(
                    message="hello",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cr"),
                )


@pytest.mark.asyncio
class TestClarificationRequesterProcess:
    async def test_returns_original_message_when_clear(self) -> None:
        llm = StubLLMProvider(["CLEAR"])
        with Tapestry() as t:
            ClarificationRequester(
                message="What is the capital of France?",
                llm=llm,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["cr"] == "What is the capital of France?"

    async def test_returns_clarifying_question_when_ambiguous(self) -> None:
        llm = StubLLMProvider(["Could you clarify what you mean by 'it'?"])
        with Tapestry() as t:
            ClarificationRequester(
                message="Can you fix it?",
                llm=llm,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["cr"] == "Could you clarify what you mean by 'it'?"

    async def test_rejects_non_string_message(self) -> None:
        llm = StubLLMProvider(["CLEAR"])
        with pytest.raises(TypeError):
            with Tapestry():
                ClarificationRequester(
                    message=42,  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="cr"),
                )
