"""``PlanStepState`` — state threaded across sequential plan-step executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class PlanStepState(PirnOpaqueValue):
    """State threaded across ``PlanExecutor``'s sequential step loop.

    The loop reads the plan and the provider of a run from this value, not from instance
    attributes on the loop knot. Inputs held on the knot break two contracts:
    ``step``/``fold`` can then only be exercised through a constructor that re-supplies
    them, not called standalone with plain values (knot-design-rules.md Rules 2 and 4),
    and the state a run records in lineage omits what the run was actually driven by. It
    is also unsafe the moment such a loop is wired into a graph that outlives one
    invocation rather than rebuilt inside its pipeline's ``process()``, since the knot
    object is then shared by every run of that graph (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating.

    Attributes:
        steps: The plan's ordered step descriptions, fixed for the loop's lifetime.
        llm: The provider each step's call runs on, fixed for the loop's lifetime.
        step_results: The LLM's output text for each completed step, in order.
        index: The index of the next step to execute.
    """

    steps: tuple[str, ...]
    llm: LLMProvider
    step_results: tuple[str, ...] = ()
    index: int = 0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "steps": list(self.steps),
            "llm": type(self.llm).__name__,
            "step_results": list(self.step_results),
            "index": self.index,
        }
