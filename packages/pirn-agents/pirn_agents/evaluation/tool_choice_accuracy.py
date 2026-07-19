"""``ToolChoiceAccuracy`` — did the agent pick the expected tools, in order?"""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.metric import Metric
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.trajectory import Trajectory
from pirn_agents.evaluation.trajectory_call_key import TrajectoryCallKey


class ToolChoiceAccuracy(Metric):
    """Score the fraction of expected steps whose tool choice the agent matched.

    Compared position-by-position against the gold trajectory::

        accuracy = correct_positions / len(expected)

    A position is correct when the actual step's ``tool_name`` equals the
    expected one (and, when ``match_arguments`` is set, its arguments match too).
    Positions beyond the actual trajectory's length count as misses, so a run
    that stops early is penalised. An empty expected trajectory scores 1.0 only
    when the actual trajectory is also empty.
    """

    def __init__(self, *, match_arguments: bool = False) -> None:
        """Configure whether arguments must also match at each position.

        Args:
            match_arguments: Also require arguments to match at each position.
        """
        self._match_arguments = match_arguments
        self._call_key = TrajectoryCallKey()

    @property
    def name(self) -> str:
        """The metric's stable identifier."""
        return "tool_choice_accuracy"

    def score(self, actual: Any, expected: Any = None) -> MetricResult:
        """Score ``actual``'s tool choices against the ``expected`` trajectory.

        Args:
            actual: The recorded agent trajectory.
            expected: The gold/expected trajectory.

        Returns:
            A :class:`MetricResult` named ``"tool_choice_accuracy"``.

        Raises:
            TypeError: If ``actual`` or ``expected`` is not a
                :class:`Trajectory`.
        """
        if not isinstance(actual, Trajectory):
            raise TypeError(
                f"ToolChoiceAccuracy: actual must be a Trajectory, got {type(actual).__name__}"
            )
        if not isinstance(expected, Trajectory):
            raise TypeError(
                f"ToolChoiceAccuracy: expected must be a Trajectory, got {type(expected).__name__}"
            )
        if len(expected) == 0:
            matched = len(actual) == 0
            return MetricResult(
                name="tool_choice_accuracy",
                score=1.0 if matched else 0.0,
                detail={"correct": 0, "expected_steps": 0, "actual_steps": len(actual)},
            )
        correct = 0
        for index, expected_step in enumerate(expected.steps):
            if index >= len(actual.steps):
                break
            actual_step = actual.steps[index]
            if actual_step.tool_name != expected_step.tool_name:
                continue
            if self._match_arguments and self._call_key.args_key(
                dict(actual_step.arguments)
            ) != self._call_key.args_key(dict(expected_step.arguments)):
                continue
            correct += 1
        return MetricResult(
            name="tool_choice_accuracy",
            score=correct / len(expected),
            detail={
                "correct": correct,
                "expected_steps": len(expected),
                "actual_steps": len(actual),
                "match_arguments": self._match_arguments,
            },
        )
