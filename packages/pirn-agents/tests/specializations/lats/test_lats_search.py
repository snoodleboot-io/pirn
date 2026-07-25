"""Tests for :class:`LatsSearch` and :class:`LatsActionProposer`."""

from __future__ import annotations

import unittest
from collections.abc import Sequence

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.specializations.lats.lats_action_proposer import LatsActionProposer
from pirn_agents.specializations.lats.lats_result import LatsResult
from pirn_agents.specializations.lats.lats_search import LatsSearch
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel
from tests.specializations.conftest import StubLLMProvider


class _KeywordValueModel(TrajectoryValueModel):
    """Values a trajectory by how many times it contains ``keyword``."""

    def __init__(self, keyword: str) -> None:
        self._keyword = keyword

    async def score(self, task: str, trajectory: Sequence[str]) -> float:
        return float(sum(1 for action in trajectory if action == self._keyword))


def _proposer_llm() -> StubLLMProvider:
    # Every expansion proposes the same two candidate actions.
    return StubLLMProvider(["- left\n- right"])


class TestLatsActionProposer(unittest.IsolatedAsyncioTestCase):
    async def test_parses_actions(self) -> None:
        llm = StubLLMProvider(["- left\n- right\n- left"])
        with Tapestry() as t:
            LatsActionProposer(task="q", llm=llm, _config=KnotConfig(id="p"))
        run = await t.run(RunRequest())
        assert run.outputs["p"] == ("left", "right")


class TestLatsSearch(unittest.IsolatedAsyncioTestCase):
    async def test_finds_highest_value_trajectory(self) -> None:
        with Tapestry() as t:
            LatsSearch(
                task="maze",
                llm=_proposer_llm(),
                value_model=_KeywordValueModel("right"),
                budget=RunBudget(max_iterations=50),
                max_depth=2,
                _config=KnotConfig(id="lats"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["lats"]
        assert isinstance(result, LatsResult)
        assert result.best_trajectory == ("right", "right")
        assert result.best_value == 2.0
        assert result.budget_exhausted is False

    async def test_value_model_is_pluggable(self) -> None:
        with Tapestry() as t:
            LatsSearch(
                task="maze",
                llm=_proposer_llm(),
                value_model=_KeywordValueModel("left"),
                budget=RunBudget(max_iterations=50),
                max_depth=2,
                _config=KnotConfig(id="lats"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["lats"]
        assert result.best_trajectory == ("left", "left")

    async def test_node_budget_bounds_search(self) -> None:
        with Tapestry() as t:
            LatsSearch(
                task="maze",
                llm=_proposer_llm(),
                value_model=_KeywordValueModel("right"),
                budget=RunBudget(max_iterations=1),
                max_depth=5,
                _config=KnotConfig(id="lats"),
            )
        run = await t.run(RunRequest())
        result = run.outputs["lats"]
        assert result.nodes_expanded == 1
        assert result.budget_exhausted is True

    async def test_deadline_only_budget_is_allowed(self) -> None:
        with Tapestry() as t:
            LatsSearch(
                task="maze",
                llm=_proposer_llm(),
                value_model=_KeywordValueModel("right"),
                budget=RunBudget(deadline_seconds=30.0),
                max_depth=2,
                _config=KnotConfig(id="lats"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        assert run.outputs["lats"].best_value == 2.0

    async def test_rejects_unbounded_budget(self) -> None:
        with Tapestry():
            knot = LatsSearch.__new__(LatsSearch)
            object.__setattr__(knot, "_config", KnotConfig(id="lats"))
        with self.assertRaises(ValueError):
            await knot.process(
                task="q",
                llm=_proposer_llm(),
                value_model=_KeywordValueModel("right"),
                budget=RunBudget(),
            )

    async def test_rejects_non_value_model(self) -> None:
        with Tapestry():
            knot = LatsSearch.__new__(LatsSearch)
            object.__setattr__(knot, "_config", KnotConfig(id="lats"))
        with self.assertRaises(TypeError):
            await knot.process(
                task="q",
                llm=_proposer_llm(),
                value_model="bad",  # type: ignore[arg-type]
                budget=RunBudget(max_iterations=5),
            )
