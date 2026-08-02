"""Tests for :class:`EvaluatorOptimizerPipeline`."""

from __future__ import annotations

import unittest

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_pipeline import (
    EvaluatorOptimizerPipeline,
)
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_result import (
    EvaluatorOptimizerResult,
)
from tests.specializations.conftest import StubLLMProvider


class TestEvaluatorOptimizerPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_on_first_when_score_meets_threshold(self) -> None:
        llm = StubLLMProvider(["cand1", "SCORE: 9\nexcellent"])
        with Tapestry() as t:
            EvaluatorOptimizerPipeline(
                task="q", llm=llm, threshold=8.0, _config=KnotConfig(id="eo")
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["eo"]
        assert isinstance(result, EvaluatorOptimizerResult)
        assert result.accepted is True
        assert result.iterations == 1
        assert result.answer == "cand1"
        assert result.score == 9.0

    async def test_refines_until_threshold_met(self) -> None:
        llm = StubLLMProvider(["c1", "SCORE: 5\nweak", "c2", "SCORE: 9\nstrong"])
        with Tapestry() as t:
            EvaluatorOptimizerPipeline(
                task="q", llm=llm, threshold=8.0, _config=KnotConfig(id="eo")
            )
        run = await t.run(RunRequest())
        result = run.outputs["eo"]
        assert result.accepted is True
        assert result.iterations == 2
        assert result.answer == "c2"
        # The second generation was fed the judge feedback from round one.
        second_gen_user = llm.calls[2][-1]["content"]
        assert "weak" in second_gen_user

    async def test_exhausts_without_acceptance(self) -> None:
        llm = StubLLMProvider(["c1", "SCORE: 3\nbad", "c2", "SCORE: 4\nmeh"])
        with Tapestry() as t:
            EvaluatorOptimizerPipeline(
                task="q",
                llm=llm,
                threshold=8.0,
                max_iterations=2,
                _config=KnotConfig(id="eo"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["eo"]
        assert result.accepted is False
        assert result.iterations == 2

    async def test_reflection_gate_early_stop(self) -> None:
        # gen, judge (below threshold), then ReflectionCheck says "no" -> stop.
        llm = StubLLMProvider(["c1", "SCORE: 3\nmeh", "no, stop here"])
        with Tapestry():
            gate = ReflectionCheck.__new__(ReflectionCheck)
            object.__setattr__(gate, "_config", KnotConfig(id="rc"))
        with Tapestry() as t:
            EvaluatorOptimizerPipeline(
                task="q",
                llm=llm,
                threshold=8.0,
                max_iterations=5,
                reflection_gate=gate,
                _config=KnotConfig(id="eo"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["eo"]
        assert result.accepted is False
        assert result.iterations == 1
        assert len(llm.calls) == 3

    async def test_rejects_non_positive_iterations(self) -> None:
        llm = StubLLMProvider(["c", "SCORE: 9"])
        with Tapestry():
            knot = EvaluatorOptimizerPipeline.__new__(EvaluatorOptimizerPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="eo"))
            object.__setattr__(knot, "_reflection_gate", None)
        with self.assertRaises(ValueError):
            await knot.process(task="q", llm=llm, max_iterations=0)


class TestEvaluatorOptimizerLoopObservability(unittest.IsolatedAsyncioTestCase):
    """Every refine iteration must be an engine-visible run.

    The loop used to be a Python `for` awaiting generator/judge/gate.process()
    directly, so the whole refinement was one opaque knot: no per-iteration
    Result, no history record, no lineage. PIR-713 ports it onto
    LoopSubTapestry by composition, so each iteration is a child run.

    (Requires PIR-773 — `LoopSubTapestry.process` was reading a stale history
    capture when nested inside a pipeline, which made all of this invisible.)
    """

    async def _run(self) -> tuple[object, InMemoryHistory]:
        history = InMemoryHistory()
        llm = StubLLMProvider(["c1", "SCORE: 5\nweak", "c2", "SCORE: 9\nstrong"])
        with Tapestry(history=history) as t:
            EvaluatorOptimizerPipeline(
                task="write",
                llm=llm,
                threshold=8.0,
                max_iterations=3,
                _config=KnotConfig(id="eo"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        return run, history

    async def test_each_iteration_is_its_own_child_run(self) -> None:
        run, history = await self._run()
        pipeline_runs = await history.children_of(run.run_id)
        loop_runs = await history.children_of(pipeline_runs[0].run_id)
        iterations = await history.children_of(loop_runs[0].run_id)
        assert [r.parent_knot_id for r in iterations] == [
            "eo_iteration_1",
            "eo_iteration_2",
        ]

    async def test_inner_knots_have_per_iteration_lineage(self) -> None:
        _, history = await self._run()
        for knot_id in ("eo_gen", "eo_judge", "eo_gate"):
            assert len(await history.query_lineage_by_knot_id(knot_id)) == 2, knot_id
