"""Tests for :class:`SelfAskPipeline`."""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.self_ask.self_ask_pipeline import SelfAskPipeline
from pirn_agents.specializations.self_ask.self_ask_result import SelfAskResult
from tests.specializations.conftest import StubLLMProvider


class _BarrierLLMProvider(LLMProvider):
    """Answers sub-questions only once every sub-question has been asked.

    The barrier deadlocks unless the sub-answer calls are genuinely in flight
    together, so this fails on a sequential loop and passes on a fan-out. The
    answer echoes the sub-question, so pairing is checked independently of the
    order the calls happen to finish in.
    """

    def __init__(self, decomposition: str, expected_subanswers: int) -> None:
        self._decomposition = decomposition
        self._barrier = asyncio.Barrier(expected_subanswers)
        self.peak_in_flight = 0
        self._in_flight = 0

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **_: Any,
    ) -> str:
        prompt = str(messages[-1]["content"])
        if prompt.startswith("who was"):
            return self._decomposition
        if prompt.startswith("Question:"):
            return "composed"
        self._in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self._in_flight)
        await self._barrier.wait()
        self._in_flight -= 1
        return f"answer-to-{prompt}"


class TestSelfAskPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_subanswers_run_concurrently_and_pair_by_position(self) -> None:
        llm = _BarrierLLMProvider("- alpha\n- beta\n- gamma", expected_subanswers=3)
        with Tapestry() as t:
            SelfAskPipeline(task="who was crowned and when?", llm=llm, _config=KnotConfig(id="sa"))
        run = await asyncio.wait_for(t.run(RunRequest()), timeout=10)
        assert run.succeeded, run.exceptions
        result = run.outputs["sa"]
        assert isinstance(result, SelfAskResult)
        assert llm.peak_in_flight == 3
        assert result.metadata.subquestions == ("alpha", "beta", "gamma")
        assert result.metadata.subanswers == (
            "answer-to-alpha",
            "answer-to-beta",
            "answer-to-gamma",
        )

    async def test_decomposes_answers_and_composes(self) -> None:
        llm = StubLLMProvider(["- who?\n- when?", "Napoleon", "1804", "Napoleon crowned in 1804"])
        with Tapestry() as t:
            SelfAskPipeline(task="who was crowned and when?", llm=llm, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["sa"]
        assert isinstance(result, SelfAskResult)
        assert result.metadata.subquestions == ("who?", "when?")
        assert result.metadata.subanswers == ("Napoleon", "1804")
        assert result.data == "Napoleon crowned in 1804"

    async def test_falls_back_to_direct_answer(self) -> None:
        # No "- " lines -> single sub-question is the task itself.
        llm = StubLLMProvider(["I have no sub-questions", "direct answer", "final"])
        with Tapestry() as t:
            SelfAskPipeline(task="what is 2+2?", llm=llm, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        result = run.outputs["sa"]
        assert result.metadata.subquestions == ("what is 2+2?",)
        assert result.data == "final"

    async def test_bounds_subquestions(self) -> None:
        llm = StubLLMProvider(["- a\n- b\n- c\n- d", "1", "2", "final"])
        with Tapestry() as t:
            SelfAskPipeline(task="q", llm=llm, max_subquestions=2, _config=KnotConfig(id="sa"))
        run = await t.run(RunRequest())
        result = run.outputs["sa"]
        assert result.metadata.subquestions == ("a", "b")

    async def test_rejects_non_positive_max(self) -> None:
        llm = StubLLMProvider(["- a", "x", "y"])
        with Tapestry():
            knot = SelfAskPipeline.__new__(SelfAskPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="sa"))
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, max_subquestions=0)
