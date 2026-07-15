"""Overhead micro-benchmark for the trajectory metrics on long trajectories.

Marked ``@pytest.mark.benchmark`` (registered in ``pyproject.toml``). It does
not depend on the pytest-benchmark plugin: wall-clock is measured directly with
:func:`time.perf_counter`. The bound is loose so it proves the metrics are
linear and cheap without being flaky. The measured figures are printed in the
``[benchmark] <name> k=v`` format the F10 report harvester parses.
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.evaluation.redundant_call_rate import redundant_call_rate
from pirn_agents.evaluation.step_efficiency import step_efficiency
from pirn_agents.evaluation.tool_choice_accuracy import tool_choice_accuracy
from pirn_agents.evaluation.trajectory import Trajectory
from pirn_agents.evaluation.trajectory_step import TrajectoryStep


@pytest.mark.benchmark
def test_trajectory_metrics_scale_on_long_trajectory() -> None:
    n = 5000
    actual = Trajectory(
        steps=[TrajectoryStep(tool_name=f"t{i % 50}", arguments={"i": i}) for i in range(n)]
    )
    expected = Trajectory(steps=[TrajectoryStep(tool_name=f"t{i % 50}") for i in range(n)])

    start = time.perf_counter()
    eff = step_efficiency(actual=actual, expected=expected)
    acc = tool_choice_accuracy(actual=actual, expected=expected)
    red = redundant_call_rate(actual)
    elapsed = time.perf_counter() - start

    assert eff.score == 1.0
    assert acc.score == 1.0
    assert red.score == 0.0
    # Three linear passes over 5k steps must be well under a second.
    assert elapsed < 1.0

    throughput = (3 * n) / elapsed if elapsed > 0 else float("inf")
    print(
        f"[benchmark] TrajectoryMetrics N={n} wall={elapsed:.4f}s "
        f"throughput={throughput:.1f} steps/s"
    )
