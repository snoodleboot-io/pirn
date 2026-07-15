"""``redundant_call_rate`` — fraction of steps that repeat an earlier call."""

from __future__ import annotations

import json

from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.trajectory import Trajectory


def redundant_call_rate(actual: Trajectory) -> MetricResult:
    """Score the fraction of steps that repeat an identical earlier call.

    A step is redundant when an earlier step already invoked the same
    ``tool_name`` with the same arguments (arguments are compared by a stable,
    order-independent JSON key)::

        rate = redundant_steps / total_steps

    Unlike the other metrics, **lower is better** — 0.0 means every call was
    distinct, higher means the agent wasted turns re-issuing calls whose answer
    it already had. An empty trajectory scores 0.0 (no redundancy).

    Args:
        actual: The recorded agent trajectory.

    Returns:
        A :class:`MetricResult` named ``"redundant_call_rate"``.

    Raises:
        TypeError: If ``actual`` is not a :class:`Trajectory`.
    """
    if not isinstance(actual, Trajectory):
        raise TypeError(
            f"redundant_call_rate: actual must be a Trajectory, got {type(actual).__name__}"
        )
    total = len(actual)
    if total == 0:
        return MetricResult(
            name="redundant_call_rate", score=0.0, detail={"total": 0, "redundant": 0}
        )
    seen: set[str] = set()
    redundant = 0
    for step in actual.steps:
        key = f"{step.tool_name}:{json.dumps(dict(step.arguments), sort_keys=True, default=str)}"
        if key in seen:
            redundant += 1
        else:
            seen.add(key)
    return MetricResult(
        name="redundant_call_rate",
        score=redundant / total,
        detail={"total": total, "redundant": redundant, "unique": len(seen)},
    )
