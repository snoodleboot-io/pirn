"""Tests for :class:`SelfAskPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.self_ask.self_ask_pipeline import SelfAskPipeline
from pirn_agents.specializations.self_ask.self_ask_result import SelfAskResult
from tests.specializations.conftest import StubLLMProvider


class TestSelfAskPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_decomposes_answers_and_composes(self) -> None:
        llm = StubLLMProvider(["- who?\n- when?", "Napoleon", "1804", "Napoleon crowned in 1804"])
        with Tapestry() as t:
            SelfAskPipeline(task="who was crowned and when?", llm=llm, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["sa"]
        assert isinstance(result, SelfAskResult)
        assert result.subquestions == ("who?", "when?")
        assert result.subanswers == ("Napoleon", "1804")
        assert result.final_answer == "Napoleon crowned in 1804"

    async def test_falls_back_to_direct_answer(self) -> None:
        # No "- " lines -> single sub-question is the task itself.
        llm = StubLLMProvider(["I have no sub-questions", "direct answer", "final"])
        with Tapestry() as t:
            SelfAskPipeline(task="what is 2+2?", llm=llm, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        result = run.outputs["sa"]
        assert result.subquestions == ("what is 2+2?",)
        assert result.final_answer == "final"

    async def test_bounds_subquestions(self) -> None:
        llm = StubLLMProvider(["- a\n- b\n- c\n- d", "1", "2", "final"])
        with Tapestry() as t:
            SelfAskPipeline(task="q", llm=llm, max_subquestions=2, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        result = run.outputs["sa"]
        assert result.subquestions == ("a", "b")

    async def test_rejects_non_positive_max(self) -> None:
        llm = StubLLMProvider(["- a", "x", "y"])
        with Tapestry():
            knot = SelfAskPipeline.__new__(SelfAskPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="sa"))
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, max_subquestions=0)
