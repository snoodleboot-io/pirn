"""``Plan`` — the ordered steps a planner intends the agent to execute.

ADR agents-speaks-core WS6b requires agents' cross-boundary value types to be
``Payload[Frame, Data]``; PIR-868 rebased the specialization results and
PIR-874 does the same for ``Plan``. It is ``Payload[PlanFrame, tuple[str, ...]]``:
the frame carries the planner's ``rationale`` and the data is the ordered
``steps`` the pipeline acts on. Read back as ``plan.metadata.rationale`` and
``plan.data``.

``Plan`` lives in ``planning/``, which must not import from
``specializations/``, so it subclasses :class:`pirn.core.payload.Payload`
directly and carries the same structural ``__eq__`` as
:class:`~pirn_agents.specializations.base.agent_result.AgentResult`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload

from pirn_agents.planning.plan_frame import PlanFrame


class Plan(Payload[PlanFrame, tuple[str, ...]]):
    """Ordered list of steps the agent intends to execute.

    Args:
        steps: Free-form step descriptions, one per intended action.
        rationale: Optional explanation the planner produced alongside the plan.
    """

    def __init__(self, steps: Sequence[str], rationale: str = "") -> None:
        super().__init__(metadata=PlanFrame(rationale=rationale), data=tuple(steps))

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if not isinstance(other, type(self)) or type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {**super()._pirn_audit_dict(), "steps": list(self.data)}
