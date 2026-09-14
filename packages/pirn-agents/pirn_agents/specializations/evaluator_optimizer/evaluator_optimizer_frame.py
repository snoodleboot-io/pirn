"""``EvaluatorOptimizerFrame`` — lineage metadata for an :class:`EvaluatorOptimizerResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class EvaluatorOptimizerFrame(PirnOpaqueValue):
    """Run-level facts for a generator/judge accept loop.

    The frame half of the ``Payload[EvaluatorOptimizerFrame, str]`` split
    (PIR-868).

    Attributes
    ----------
    score:
        The judge score of the answer on the 0-10 scale.
    accepted:
        Whether the accept gate fired (``score`` met the threshold) before the
        iteration cap.
    iterations:
        Number of generate/judge rounds performed.
    """

    score: float
    accepted: bool
    iterations: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "accepted": self.accepted,
            "iterations": self.iterations,
        }
