"""LATS budget-vs-quality micro-benchmark (PIR-243).

``@pytest.mark.benchmark``; a larger node budget lets the bounded search reach a
higher-value trajectory, and the search never exceeds its node budget.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.specializations.lats.lats_search import LatsSearch
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubLLMProvider


class _DepthValueModel(TrajectoryValueModel):
    async def score(self, task: str, trajectory: Sequence[str]) -> float:
        return float(sum(1 for action in trajectory if action == "right"))


async def _run(node_budget: int, max_depth: int) -> tuple[float, int, bool]:
    with Tapestry() as t:
        LatsSearch(
            task="maze",
            llm=StubLLMProvider(["- left\n- right"]),
            value_model=_DepthValueModel(),
            budget=RunBudget(max_iterations=node_budget),
            max_depth=max_depth,
            _config=KnotConfig(id="lats"),
        )
    run = await t.run(RunRequest())
    result = run.outputs["lats"]
    return result.best_value, result.nodes_expanded, result.budget_exhausted


@pytest.mark.benchmark
async def test_lats_budget_quality_tradeoff(benchmark_recorder: BenchmarkRecorder) -> None:
    small_value, small_nodes, small_exhausted = await _run(node_budget=1, max_depth=4)
    large_value, large_nodes, large_exhausted = await _run(node_budget=100, max_depth=4)

    # Node budget is strictly honoured ...
    assert small_nodes <= 1
    assert small_exhausted is True
    # ... and a larger budget reaches a better trajectory.
    assert large_value >= small_value
    assert large_exhausted is False

    benchmark_recorder.record(
        "LatsBudgetQuality",
        small_budget_value=small_value,
        large_budget_value=large_value,
        large_nodes_expanded=float(large_nodes),
    )
    report = benchmark_recorder.report()
    assert report.metric("LatsBudgetQuality", "large_budget_value") is not None
