"""Unit tests for :class:`SelfConsistencyEnsemble`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.chain_of_thought.self_consistency_ensemble import (
    SelfConsistencyEnsemble,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestSelfConsistencyEnsembleProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_majority_vote_answer(self) -> None:
        llm = StubLLMProvider(["Paris", "Paris", "London"])
        with Tapestry() as t:
            SelfConsistencyEnsemble(
                prompt="Capital of France?",
                llm=llm,
                samples=3,
                _config=KnotConfig(id="sce"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["sce"]
        assert isinstance(response, AgentResponse)
        assert response.content == "Paris"

    async def test_makes_n_llm_calls(self) -> None:
        llm = StubLLMProvider(["yes"] * 4)
        with Tapestry() as t:
            SelfConsistencyEnsemble(
                prompt="q",
                llm=llm,
                samples=4,
                _config=KnotConfig(id="sce"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 4

    async def test_single_sample_returns_that_answer(self) -> None:
        llm = StubLLMProvider(["only answer"])
        with Tapestry() as t:
            SelfConsistencyEnsemble(
                prompt="q",
                llm=llm,
                samples=1,
                _config=KnotConfig(id="sce"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sce"].content == "only answer"


class TestSelfConsistencyEnsembleConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                SelfConsistencyEnsemble(
                    prompt="q",
                    llm=object(),  # type: ignore[arg-type]
                    _config=KnotConfig(id="sce"),
                )

    async def test_rejects_zero_samples(self) -> None:
        llm = StubLLMProvider(["x"])
        with self.assertRaisesRegex(ValueError, "samples must be a positive int"):
            with Tapestry():
                SelfConsistencyEnsemble(
                    prompt="q",
                    llm=llm,
                    samples=0,
                    _config=KnotConfig(id="sce"),
                )
