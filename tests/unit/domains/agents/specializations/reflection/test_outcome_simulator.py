"""Unit tests for :class:`OutcomeSimulator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.reflection.outcome_simulator import (
    OutcomeSimulator,
    SimulationResult,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


_SIMULATION_RESPONSE = (
    "Best case:\nEverything works perfectly.\n"
    "Neutral case:\nPartial success with minor issues.\n"
    "Worst case:\nComplete failure and rollback required."
)


class TestOutcomeSimulatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_simulation_result_with_three_cases(self) -> None:
        llm = StubLLMProvider([_SIMULATION_RESPONSE])
        with Tapestry() as t:
            OutcomeSimulator(
                action="Deploy new service to production.",
                llm=llm,
                _config=KnotConfig(id="sim"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        sim = result.outputs["sim"]
        assert isinstance(sim, SimulationResult)
        assert "perfectly" in sim.best_case
        assert "minor" in sim.neutral_case
        assert "failure" in sim.worst_case

    async def test_missing_section_yields_empty_string(self) -> None:
        llm = StubLLMProvider(["Best case:\nGood outcome."])
        with Tapestry() as t:
            OutcomeSimulator(
                action="Do something.",
                llm=llm,
                _config=KnotConfig(id="sim"),
            )
        result = await t.run(RunRequest())
        sim = result.outputs["sim"]
        assert sim.neutral_case == ""
        assert sim.worst_case == ""
        assert "Good outcome" in sim.best_case

    async def test_makes_one_llm_call(self) -> None:
        llm = StubLLMProvider([_SIMULATION_RESPONSE])
        with Tapestry() as t:
            OutcomeSimulator(
                action="action",
                llm=llm,
                _config=KnotConfig(id="sim"),
            )
        await t.run(RunRequest())
        assert len(llm.calls) == 1


class TestOutcomeSimulatorConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                OutcomeSimulator(
                    action="action",
                    llm=0,  # type: ignore[arg-type]
                    _config=KnotConfig(id="sim"),
                )
