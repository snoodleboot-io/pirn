"""Unit tests for :class:`PlanExecutor`.

PIR-867: ``PlanExecutor`` is a ``SubTapestry`` now — each step depends on every
prior step's result, so ``process`` wires a ``LoopSubTapestry``
(``PlanStepLoop``) rather than awaiting ``llm.chat`` in a hand-rolled ``for``
loop. ``process`` therefore returns the sink of an inner pipeline instead of
the ``AgentResponse`` directly, so the outcome tests run a real tapestry and
read the executor's output (the same pattern PIR-856 established for
``ParallelToolCaller``). Input-validation tests still exercise the guard via
the engine's own IO validation, since there is no longer a value to compute
before it fires.
"""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.planning.plan import Plan
from pirn_agents.specializations.plan_and_execute.plan_executor import PlanExecutor
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


@KnotFactory.knot
async def emit_plan() -> Plan:
    return Plan(steps=("step one", "step two", "step three"))


def _make_knot(llm: StubLLMProvider) -> PlanExecutor:
    with Tapestry():
        return PlanExecutor(plan=Plan(steps=()), llm=llm, _config=KnotConfig(id="exec"))


class TestPlanExecutorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_executes_each_step_and_returns_combined_response(self) -> None:
        llm = StubLLMProvider(["result-one", "result-two", "result-three"])
        plan = Plan(steps=("step one", "step two", "step three"))
        with Tapestry() as t:
            PlanExecutor(plan=plan, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert "result-one" in response.data
        assert "result-two" in response.data
        assert "result-three" in response.data

    async def test_makes_one_call_per_step(self) -> None:
        llm = StubLLMProvider(["r1", "r2"])
        plan = Plan(steps=("a", "b"))
        with Tapestry() as t:
            PlanExecutor(plan=plan, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert len(llm.calls) == 2

    async def test_empty_plan_returns_empty_content(self) -> None:
        llm = StubLLMProvider([])
        plan = Plan(steps=())
        with Tapestry() as t:
            PlanExecutor(plan=plan, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert response.data == ""

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(["r"])
        k = _make_knot(llm)
        plan = Plan(steps=("a",))
        result = await k({"plan": plan, "llm": "bad"})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_plan(self) -> None:
        llm = StubLLMProvider(["r"])
        k = _make_knot(llm)
        result = await k({"plan": "not-a-plan", "llm": llm})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_each_step_gets_its_own_lineage_row(self) -> None:
        """PIR-867: each step is a node now, not an inline await in a for loop.

        Nesting is three deep here: ``exec`` (the outer ``PlanExecutor``) runs
        ``loop`` (a ``LoopSubTapestry``) whose own inner run registers one
        ``_IterationChainKnot`` per step, each of which runs the per-step
        tapestry containing the ``call`` knot — so the search walks every
        descendant run, not just direct children.
        """
        llm = StubLLMProvider(["result-one"])
        plan = Plan(steps=("only step",))
        with Tapestry() as t:
            PlanExecutor(plan=plan, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        inner_knot_ids: set[str] = set()
        frontier = [result.run_id]
        while frontier:
            run_id = frontier.pop()
            for child in await t.history.children_of(run_id):
                inner_knot_ids.update(row.knot_id for row in child.lineage)
                frontier.append(child.run_id)
        assert "call" in inner_knot_ids, inner_knot_ids

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["result-one", "result-two", "result-three"])
        with Tapestry() as t:
            p = emit_plan(_config=KnotConfig(id="p"))
            PlanExecutor(plan=p, llm=llm, _config=KnotConfig(id="exec"))
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["exec"]
        assert isinstance(response, AgentResponse)
        assert "result-one" in response.data


if __name__ == "__main__":
    unittest.main()
