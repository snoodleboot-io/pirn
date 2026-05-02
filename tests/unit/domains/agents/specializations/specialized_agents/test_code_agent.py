"""Tests for :class:`CodeAgent`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents.code_agent import (
    CodeAgent,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


@pytest.mark.asyncio
class TestCodeAgentConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                CodeAgent(
                    task="write a function",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="code"),
                )

    async def test_rejects_empty_language(self) -> None:
        llm = StubLLMProvider(["def f(): pass"])
        with pytest.raises(TypeError, match="language"):
            with Tapestry():
                CodeAgent(
                    task="write a function",
                    llm=llm,
                    language="",
                    _config=KnotConfig(id="code"),
                )


@pytest.mark.asyncio
class TestCodeAgentHappyPath:
    async def test_returns_code_in_content(self) -> None:
        llm = StubLLMProvider(["def add(a, b):\n    return a + b\n"])
        with Tapestry() as t:
            CodeAgent(
                task="write add function",
                llm=llm,
                language="python",
                _config=KnotConfig(id="code"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["code"]
        assert isinstance(response, AgentResponse)
        assert "def add" in response.content
        assert response.usage["lint_warnings"] == 0
        assert response.usage["tests_skipped"] == 1

    async def test_lint_flags_python_syntax_error(self) -> None:
        # Output is not valid python; lint warnings should be non-zero.
        llm = StubLLMProvider(["def add(a, b):\n    return a +\n"])
        with Tapestry() as t:
            CodeAgent(
                task="write add function",
                llm=llm,
                language="python",
                _config=KnotConfig(id="code"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["code"]
        assert isinstance(response, AgentResponse)
        assert response.usage["lint_warnings"] >= 1
