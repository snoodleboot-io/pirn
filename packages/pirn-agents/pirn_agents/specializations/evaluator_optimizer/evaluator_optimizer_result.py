"""``EvaluatorOptimizerResult`` — the typed outcome of an accept-loop run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvaluatorOptimizerResult(PirnOpaqueValue):
    """Outcome of a generator/judge accept loop.

    Attributes
    ----------
    answer:
        The best candidate produced.
    score:
        The judge score of ``answer`` on the 0-10 scale.
    accepted:
        Whether the accept gate fired (``score`` met the threshold) before the
        iteration cap.
    iterations:
        Number of generate/judge rounds performed.
    """

    answer: str
    score: float
    accepted: bool
    iterations: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "score": self.score,
            "accepted": self.accepted,
            "iterations": self.iterations,
        }
