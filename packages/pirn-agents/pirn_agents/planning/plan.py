"""A plan produced by the planning layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class Plan(PirnOpaqueValue):
    """Ordered list of steps the agent intends to execute.

    Attributes
    ----------
    steps:
        Tuple of free-form step descriptions, one per intended action.
    rationale:
        Optional explanation the planner produced alongside the plan;
        useful for logging and reflection knots.
    """

    steps: tuple[str, ...]
    rationale: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "steps": list(self.steps),
            "rationale": self.rationale,
        }
