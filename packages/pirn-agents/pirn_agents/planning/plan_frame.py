"""``PlanFrame`` — lineage metadata for a :class:`~pirn_agents.planning.plan.Plan`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class PlanFrame(PirnOpaqueValue):
    """Planner-level facts about a plan.

    The frame half of the ``Payload[PlanFrame, tuple[str, ...]]`` split
    (PIR-868, PIR-874).

    Attributes
    ----------
    rationale:
        Optional explanation the planner produced alongside the plan; useful
        for logging and reflection knots.
    """

    rationale: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"rationale": self.rationale}
