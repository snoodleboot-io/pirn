"""``SimulationResult`` — structured outcome record from :class:`OutcomeSimulator`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SimulationResult(PirnOpaqueValue):
    """Structured outcome simulation for a proposed action.

    Attributes:
        best_case: Description of the most favourable plausible outcome.
        neutral_case: Description of the most likely / neutral outcome.
        worst_case: Description of the most adverse plausible outcome.
    """

    best_case: str
    neutral_case: str
    worst_case: str

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "best_case": self.best_case,
            "neutral_case": self.neutral_case,
            "worst_case": self.worst_case,
        }
