"""``ReflexionEvaluationFrame`` — the verdict half of a :class:`ReflexionEvaluation` (PIR-868, PIR-874)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ReflexionEvaluationFrame(PirnOpaqueValue):
    """Whether a single actor attempt satisfied the task.

    Attributes
    ----------
    success:
        Whether the attempt is judged to satisfy the task.
    """

    success: bool

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"success": self.success}
