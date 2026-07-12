"""``ReflexionResult`` — the typed outcome of a Reflexion run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt


@dataclass(frozen=True)
class ReflexionResult(PirnOpaqueValue):
    """Outcome of a bounded Reflexion loop.

    Attributes
    ----------
    answer:
        The best/last answer produced.
    succeeded:
        Whether the evaluator accepted an attempt before the iteration cap.
    iterations:
        Number of actor attempts made (1-based count).
    attempts:
        The per-attempt records, in order.
    """

    answer: str
    succeeded: bool
    iterations: int
    attempts: tuple[ReflexionAttempt, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "succeeded": self.succeeded,
            "iterations": self.iterations,
            "attempts": [attempt._pirn_audit_dict() for attempt in self.attempts],
        }
