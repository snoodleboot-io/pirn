"""``ReflexionEvaluation`` — the evaluator's verdict on one Reflexion attempt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ReflexionEvaluation(PirnOpaqueValue):
    """Outcome of evaluating a single actor attempt.

    Attributes
    ----------
    success:
        Whether the attempt is judged to satisfy the task.
    feedback:
        Free-form feedback describing what to improve when ``success`` is
        ``False``; empty on success.
    """

    success: bool
    feedback: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"success": self.success, "feedback": self.feedback}
