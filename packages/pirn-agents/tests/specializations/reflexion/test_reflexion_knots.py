"""Tests for the Reflexion constituent knots (actor / evaluator / reflector)."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.reflexion.reflexion_actor import ReflexionActor
from pirn_agents.specializations.reflexion.reflexion_evaluation import ReflexionEvaluation
from pirn_agents.specializations.reflexion.reflexion_evaluator import ReflexionEvaluator
from pirn_agents.specializations.reflexion.reflexion_reflector import ReflexionReflector
from tests.specializations.conftest import StubLLMProvider


class TestReflexionActor(unittest.IsolatedAsyncioTestCase):
    async def test_returns_answer(self) -> None:
        llm = StubLLMProvider(["my answer"])
        with Tapestry() as t:
            ReflexionActor(task="q", llm=llm, _config=KnotConfig(id="actor"))
        run = await t.run(RunRequest())
        assert run.outputs["actor"] == "my answer"

    async def test_reflections_injected_into_prompt(self) -> None:
        llm = StubLLMProvider(["answer"])
        with Tapestry():
            actor = ReflexionActor(task="q", llm=llm, _config=KnotConfig(id="actor"))
        await actor.process(task="q", llm=llm, reflections=("lesson-one",))
        system = llm.calls[0][0]["content"]
        assert "lesson-one" in system

    async def test_rejects_non_llm(self) -> None:
        with Tapestry():
            actor = ReflexionActor.__new__(ReflexionActor)
            object.__setattr__(actor, "_config", KnotConfig(id="a"))
        with self.assertRaises(TypeError):
            await actor.process(task="q", llm="bad")  # type: ignore[arg-type]


class TestReflexionEvaluator(unittest.IsolatedAsyncioTestCase):
    async def test_pass_is_success(self) -> None:
        llm = StubLLMProvider(["PASS"])
        with Tapestry() as t:
            ReflexionEvaluator(task="q", answer="a", llm=llm, _config=KnotConfig(id="ev"))
        run = await t.run(RunRequest())
        out = run.outputs["ev"]
        assert isinstance(out, ReflexionEvaluation)
        assert out.success is True

    async def test_fail_carries_feedback(self) -> None:
        llm = StubLLMProvider(["FAIL: too short"])
        with Tapestry() as t:
            ReflexionEvaluator(task="q", answer="a", llm=llm, _config=KnotConfig(id="ev"))
        run = await t.run(RunRequest())
        out = run.outputs["ev"]
        assert out.success is False
        assert out.feedback == "too short"


class TestReflexionReflector(unittest.IsolatedAsyncioTestCase):
    async def test_returns_reflection(self) -> None:
        llm = StubLLMProvider(["be more precise"])
        with Tapestry() as t:
            ReflexionReflector(
                task="q", answer="a", feedback="wrong", llm=llm, _config=KnotConfig(id="rf")
            )
        run = await t.run(RunRequest())
        assert run.outputs["rf"] == "be more precise"
