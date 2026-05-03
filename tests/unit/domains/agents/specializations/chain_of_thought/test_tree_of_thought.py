"""Unit tests for :class:`TreeOfThought`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.chain_of_thought.tree_of_thought import (
    TreeOfThought,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


@pytest.mark.asyncio
class TestTreeOfThoughtProcess:
    async def test_returns_agent_response(self) -> None:
        llm = StubLLMProvider(["thought"] * 20 + ["8"] * 20)
        with Tapestry() as t:
            TreeOfThought(
                prompt="Solve this.",
                llm=llm,
                k_candidates=2,
                beam_width=1,
                depth=1,
                _config=KnotConfig(id="tot"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["tot"]
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0

    async def test_scores_determine_best_path(self) -> None:
        responses = ["path-A", "path-B", "10", "1"]
        llm = StubLLMProvider(responses)
        with Tapestry() as t:
            TreeOfThought(
                prompt="start",
                llm=llm,
                k_candidates=2,
                beam_width=1,
                depth=1,
                _config=KnotConfig(id="tot"),
            )
        result = await t.run(RunRequest())
        response = result.outputs["tot"]
        assert isinstance(response, AgentResponse)
        assert "path-A" in response.content


@pytest.mark.asyncio
class TestTreeOfThoughtConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        with pytest.raises(TypeError, match="LLMProvider"):
            with Tapestry():
                TreeOfThought(
                    prompt="q",
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="tot"),
                )

    async def test_rejects_zero_depth(self) -> None:
        llm = StubLLMProvider(["x"])
        with pytest.raises(ValueError, match="depth must be a positive int"):
            with Tapestry():
                TreeOfThought(
                    prompt="q",
                    llm=llm,
                    depth=0,
                    _config=KnotConfig(id="tot"),
                )

    async def test_rejects_zero_k_candidates(self) -> None:
        llm = StubLLMProvider(["x"])
        with pytest.raises(ValueError, match="k_candidates must be a positive int"):
            with Tapestry():
                TreeOfThought(
                    prompt="q",
                    llm=llm,
                    k_candidates=0,
                    _config=KnotConfig(id="tot"),
                )

    async def test_rejects_zero_beam_width(self) -> None:
        llm = StubLLMProvider(["x"])
        with pytest.raises(ValueError, match="beam_width must be a positive int"):
            with Tapestry():
                TreeOfThought(
                    prompt="q",
                    llm=llm,
                    beam_width=0,
                    _config=KnotConfig(id="tot"),
                )
