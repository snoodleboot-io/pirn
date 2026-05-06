"""Unit tests for :class:`SelfConsistencyEnsemble`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.chain_of_thought.self_consistency_ensemble import (
    SelfConsistencyEnsemble,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> SelfConsistencyEnsemble:
    with Tapestry():
        return SelfConsistencyEnsemble(
            prompt="x",
            llm=llm,
            samples=3,
            _config=KnotConfig(id="sce"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_majority_vote_answer(self) -> None:
        llm = StubLLMProvider(["Paris", "Paris", "London"])
        k = _make_knot(llm)
        response = await k.process(prompt="Capital of France?", llm=llm, samples=3)
        assert isinstance(response, AgentResponse)
        assert response.content == "Paris"

    async def test_makes_n_llm_calls(self) -> None:
        llm = StubLLMProvider(["yes"] * 4)
        k = _make_knot(llm)
        await k.process(prompt="q", llm=llm, samples=4)
        assert len(llm.calls) == 4

    async def test_single_sample_returns_that_answer(self) -> None:
        llm = StubLLMProvider(["only answer"])
        k = _make_knot(llm)
        response = await k.process(prompt="q", llm=llm, samples=1)
        assert response.content == "only answer"

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                prompt="q",
                llm=object(),  # type: ignore[arg-type]
                samples=3,
            )

    async def test_rejects_zero_samples(self) -> None:
        llm = StubLLMProvider(["x"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "samples must be a positive int"):
            await k.process(prompt="q", llm=llm, samples=0)
