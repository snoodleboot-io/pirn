"""``PlanStepState`` — state threaded across sequential plan-step executions."""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass
class PlanStepState:
    """State threaded across ``PlanExecutor``'s sequential step loop.

    Attributes
    ----------
    steps:
        The plan's ordered step descriptions, fixed for the loop's lifetime.
    step_results:
        The LLM's output text for each completed step, in order.
    index:
        The index of the next step to execute.
    llm:
        The provider each step calls. It travels in the state, not on the loop
        instance, so the loop holds no per-run input (knot-design-rules Rule 4).
    """

    steps: tuple[str, ...]
    llm: LLMProvider
    step_results: tuple[str, ...] = ()
    index: int = 0
