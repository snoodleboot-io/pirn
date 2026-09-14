"""``_PlanStepState`` — state threaded across sequential plan-step executions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _PlanStepState:
    """State threaded across ``PlanExecutor``'s sequential step loop.

    Attributes
    ----------
    steps:
        The plan's ordered step descriptions, fixed for the loop's lifetime.
    step_results:
        The LLM's output text for each completed step, in order.
    index:
        The index of the next step to execute.
    """

    steps: tuple[str, ...]
    step_results: tuple[str, ...] = ()
    index: int = 0
