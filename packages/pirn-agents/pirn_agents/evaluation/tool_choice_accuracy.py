"""``tool_choice_accuracy`` — did the agent pick the expected tools, in order?"""

from __future__ import annotations

import json

from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.trajectory import Trajectory


def _args_key(step_arguments: object) -> str:
    """Return a stable, order-independent key for a step's arguments."""
    return json.dumps(step_arguments, sort_keys=True, default=str)


def tool_choice_accuracy(
    *,
    actual: Trajectory,
    expected: Trajectory,
    match_arguments: bool = False,
) -> MetricResult:
    """Score the fraction of expected steps whose tool choice the agent matched.

    Compared position-by-position against the gold trajectory::

        accuracy = correct_positions / len(expected)

    A position is correct when the actual step's ``tool_name`` equals the
    expected one (and, when ``match_arguments`` is set, its arguments match too).
    Positions beyond the actual trajectory's length count as misses, so a run
    that stops early is penalised. An empty expected trajectory scores 1.0 only
    when the actual trajectory is also empty.

    Args:
        actual: The recorded agent trajectory.
        expected: The gold/expected trajectory.
        match_arguments: Also require arguments to match at each position.

    Returns:
        A :class:`MetricResult` named ``"tool_choice_accuracy"``.

    Raises:
        TypeError: If ``actual`` or ``expected`` is not a :class:`Trajectory`.
    """
    if not isinstance(actual, Trajectory):
        raise TypeError(
            f"tool_choice_accuracy: actual must be a Trajectory, got {type(actual).__name__}"
        )
    if not isinstance(expected, Trajectory):
        raise TypeError(
            f"tool_choice_accuracy: expected must be a Trajectory, got {type(expected).__name__}"
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
        if match_arguments and _args_key(dict(actual_step.arguments)) != _args_key(
            dict(expected_step.arguments)
        ):
            continue
        correct += 1
    return MetricResult(
        name="tool_choice_accuracy",
        score=correct / len(expected),
        detail={
            "correct": correct,
            "expected_steps": len(expected),
            "actual_steps": len(actual),
            "match_arguments": match_arguments,
        },
    )
