"""``step_efficiency`` — how economical the run was versus the gold path."""

from __future__ import annotations

from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.trajectory import Trajectory


def step_efficiency(*, actual: Trajectory, expected: Trajectory) -> MetricResult:
    """Score how few steps the agent used relative to the expected path.

    Formula::

        efficiency = min(1.0, len(expected) / len(actual))

    Taking the expected number of steps (or fewer) scores 1.0; taking extra
    steps drives the score down proportionally. A run that took no steps scores
    1.0 only when the expected path is also empty (nothing was required).

    Args:
        actual: The recorded agent trajectory.
        expected: The gold/expected trajectory (its length is the ideal budget).

    Returns:
        A :class:`MetricResult` named ``"step_efficiency"``.

    Raises:
        TypeError: If ``actual`` or ``expected`` is not a :class:`Trajectory`.
    """
    if not isinstance(actual, Trajectory):
        raise TypeError(
            f"step_efficiency: actual must be a Trajectory, got {type(actual).__name__}"
        )
    if not isinstance(expected, Trajectory):
        raise TypeError(
            f"step_efficiency: expected must be a Trajectory, got {type(expected).__name__}"
        )
    actual_steps = len(actual)
    expected_steps = len(expected)
    if actual_steps == 0:
        score = 1.0 if expected_steps == 0 else 0.0
    else:
        score = min(1.0, expected_steps / actual_steps)
    return MetricResult(
        name="step_efficiency",
        score=score,
        detail={"actual_steps": actual_steps, "expected_steps": expected_steps},
    )
