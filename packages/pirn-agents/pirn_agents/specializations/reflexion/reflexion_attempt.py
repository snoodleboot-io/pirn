"""``ReflexionAttempt`` — the record of one actor/evaluator/reflection cycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ReflexionAttempt(PirnOpaqueValue):
    """One attempt in a Reflexion run.

    Attributes
    ----------
    answer:
        The actor's answer for this attempt.
    success:
        The evaluator's verdict for ``answer``.
    feedback:
        The evaluator's feedback for ``answer``.
    reflection:
        The verbal self-reflection written to memory after a failed attempt;
        empty on the successful (final) attempt.
    """

    answer: str
    success: bool
    feedback: str = ""
    reflection: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "success": self.success,
            "feedback": self.feedback,
            "reflection": self.reflection,
        }
