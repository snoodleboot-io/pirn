"""Tests for :class:`PromptChainPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.prompt_chaining.prompt_chain_pipeline import PromptChainPipeline
from pirn_agents.specializations.prompt_chaining.prompt_chain_result import PromptChainResult
from tests.specializations.conftest import StubLLMProvider


class TestPromptChainPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_chains_outputs_in_order(self) -> None:
        llm = StubLLMProvider(["summary", "french translation"])
        with Tapestry() as t:
            PromptChainPipeline(
                task="long document",
                llm=llm,
                steps=("Summarise", "Translate to French"),
                _config=KnotConfig(id="pc"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["pc"]
        assert isinstance(result, PromptChainResult)
        assert result.outputs == ("summary", "french translation")
        assert result.final == "french translation"

    async def test_each_link_feeds_the_next(self) -> None:
        llm = StubLLMProvider(["step1out", "step2out"])
        with Tapestry() as t:
            PromptChainPipeline(task="seed", llm=llm, steps=("a", "b"), _config=KnotConfig(id="pc"))
        await t.run(RunRequest())
        # Link 1 sees the seed; link 2 sees link 1's output.
        assert llm.calls[0][-1]["content"] == "seed"
        assert llm.calls[1][-1]["content"] == "step1out"

    async def test_rejects_empty_steps(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            knot = PromptChainPipeline.__new__(PromptChainPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="pc"))
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, steps=())

    async def test_rejects_non_llm(self) -> None:
        with Tapestry():
            knot = PromptChainPipeline.__new__(PromptChainPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="pc"))
        with self.assertRaises(TypeError):
            await knot.process(task="q", llm="bad", steps=("a",))  # type: ignore[arg-type]
