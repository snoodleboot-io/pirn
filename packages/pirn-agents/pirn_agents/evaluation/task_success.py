"""``TaskSuccess`` — did the run reach the expected end-state?"""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.metric import Metric
from pirn_agents.evaluation.metric_result import MetricResult


class TaskSuccess(Metric):
    """Score 1.0 when the observed outcome equals the expected outcome, else 0.0.

    Type-agnostic, unlike :class:`~pirn_agents.evaluation.exact_match.ExactMatch`:
    it compares whole *outcomes* by equality, so it covers a boolean success
    flag (``TaskSuccess().score(agent_succeeded)`` against the default
    ``expected=True``) as well as a structured end-state
    (``TaskSuccess().score(final_state, goal_state)``). No normalisation is
    applied — the comparison is exact ``==``.
    """

    def __init__(self, *, expected: Any = True) -> None:
        """Configure the default outcome that counts as success.

        Args:
            expected: The outcome that counts as success; defaults to ``True`` so
                a bare boolean flag can be scored directly.
        """
        self._expected = expected

    @property
    def name(self) -> str:
        """The metric's stable identifier."""
        return "task_success"

    def score(self, actual: Any, expected: Any = None) -> MetricResult:
        """Score 1.0 when ``actual`` equals the expected outcome, else 0.0.

        Args:
            actual: The observed outcome (a bool flag, a value, or any comparable
                object).
            expected: The outcome that counts as success; when ``None`` the
                configured default is used.

        Returns:
            A :class:`MetricResult` named ``"task_success"`` with score
            ``1.0``/``0.0`` and string renderings of both outcomes in ``detail``.
        """
        target = expected if expected is not None else self._expected
        succeeded = actual == target
        return MetricResult(
            name="task_success",
            score=1.0 if succeeded else 0.0,
            detail={"actual": repr(actual), "expected": repr(target)},
        )
