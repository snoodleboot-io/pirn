"""Tests for the Evaluator-Optimizer knots (generator / judge / accept gate)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.evaluator_optimizer.accept_gate import AcceptGate
from pirn_agents.specializations.evaluator_optimizer.candidate_generator import CandidateGenerator
from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.evaluator_optimizer.llm_judge import LlmJudge
from tests.specializations.conftest import StubLLMProvider


class TestCandidateGenerator(unittest.IsolatedAsyncioTestCase):
    async def test_generates_candidate(self) -> None:
        llm = StubLLMProvider(["draft"])
        with Tapestry() as t:
            CandidateGenerator(task="q", llm=llm, _config=KnotConfig(id="g"))
        run = await t.run(RunRequest())
        assert run.outputs["g"] == "draft"

    async def test_feedback_included_in_prompt(self) -> None:
        llm = StubLLMProvider(["draft"])
        with Tapestry():
            gen = CandidateGenerator(task="q", llm=llm, _config=KnotConfig(id="g"))
        await gen.process(task="q", llm=llm, feedback="add examples")
        user = llm.calls[0][-1]["content"]
        assert "add examples" in user


class TestLlmJudge(unittest.IsolatedAsyncioTestCase):
    async def test_parses_score_and_feedback(self) -> None:
        llm = StubLLMProvider(["SCORE: 7\nneeds more detail"])
        with Tapestry() as t:
            LlmJudge(task="q", candidate="c", llm=llm, _config=KnotConfig(id="j"))
        run = await t.run(RunRequest())
        verdict = run.outputs["j"]
        assert isinstance(verdict, JudgeVerdict)
        assert verdict.score == 7.0
        assert "needs more detail" in verdict.feedback

    async def test_clamps_and_defaults_score(self) -> None:
        with Tapestry():
            judge = LlmJudge(
                task="q", candidate="c", llm=StubLLMProvider([""]), _config=KnotConfig(id="j")
            )
        assert LlmJudge._parse_score("SCORE: 42") == 10.0
        assert LlmJudge._parse_score("no number here") == 0.0
        assert judge is not None


class TestAcceptGate(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_at_threshold(self) -> None:
        with Tapestry():
            gate = AcceptGate(
                verdict=JudgeVerdict(score=8.0), threshold=8.0, _config=KnotConfig(id="gate")
            )
        assert await gate.process(verdict=JudgeVerdict(score=8.0), threshold=8.0) is True
        assert await gate.process(verdict=JudgeVerdict(score=7.9), threshold=8.0) is False

    async def test_rejects_non_verdict(self) -> None:
        with Tapestry():
            gate = AcceptGate(
                verdict=JudgeVerdict(score=0.0), threshold=8.0, _config=KnotConfig(id="gate")
            )
        with self.assertRaises(TypeError):
            await gate.process(verdict="bad", threshold=8.0)  # type: ignore[arg-type]
