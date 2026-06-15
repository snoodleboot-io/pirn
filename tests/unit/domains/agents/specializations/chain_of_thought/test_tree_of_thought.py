"""Unit tests for :class:`TreeOfThought`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_agents.specializations.chain_of_thought.tree_of_thought import (
    TreeOfThought,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> TreeOfThought:
    with Tapestry():
        return TreeOfThought(
            prompt="x",
            llm=llm,
            k_candidates=2,
            beam_width=1,
            depth=1,
            _config=KnotConfig(id="tot"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_agent_response(self) -> None:
        llm = StubLLMProvider(["thought"] * 20 + ["8"] * 20)
        k = _make_knot(llm)
        response = await k.process(
            prompt="Solve this.",
            llm=llm,
            k_candidates=2,
            beam_width=1,
            depth=1,
        )
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0

    async def test_scores_determine_best_path(self) -> None:
        responses = ["path-A", "path-B", "10", "1"]
        llm = StubLLMProvider(responses)
        k = _make_knot(llm)
        response = await k.process(
            prompt="start",
            llm=llm,
            k_candidates=2,
            beam_width=1,
            depth=1,
        )
        assert isinstance(response, AgentResponse)
        assert "path-A" in response.content

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                prompt="q",
                llm="bad",  # type: ignore[arg-type]
                k_candidates=2,
                beam_width=1,
                depth=1,
            )

    async def test_rejects_zero_depth(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "depth must be a positive int"):
            await k.process(
                prompt="q",
                llm=llm,
                k_candidates=2,
                beam_width=1,
                depth=0,
            )
