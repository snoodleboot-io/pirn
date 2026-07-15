"""``task_success`` — did the run reach the expected end-state?"""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.metric_result import MetricResult


def task_success(actual: Any, *, expected: Any = True) -> MetricResult:
    """Score 1.0 when the observed outcome equals the expected outcome, else 0.0.

    Type-agnostic, unlike :func:`~pirn_agents.evaluation.exact_match.exact_match`:
    it compares whole *outcomes* by equality, so it covers a boolean success
    flag (``task_success(agent_succeeded)`` against the default ``expected=True``)
    as well as a structured end-state (``task_success(final_state,
    expected=goal_state)``). No normalisation is applied — the comparison is
    exact ``==``.

    Args:
        actual: The observed outcome (a bool flag, a value, or any comparable
            object).
        expected: The outcome that counts as success; defaults to ``True`` so a
            bare boolean flag can be passed positionally.

    Returns:
        A :class:`MetricResult` named ``"task_success"`` with score ``1.0``/``0.0``
        and string renderings of both outcomes in ``detail``.
    """
    succeeded = actual == expected
    return MetricResult(
        name="task_success",
        score=1.0 if succeeded else 0.0,
        detail={"actual": repr(actual), "expected": repr(expected)},
    )
