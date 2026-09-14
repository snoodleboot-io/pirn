"""``SimulationFrame`` — lineage metadata for a :class:`SimulationResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SimulationFrame(PirnOpaqueValue):
    """Run-level context for a proposed action's outcome simulation.

    The frame half of the ``Payload[SimulationFrame, str]`` split (PIR-868):
    carries the two bracketing scenarios, leaving the worst case — the one
    most likely to drive a caller's decision — as the payload's ``data``.

    Attributes
    ----------
    best_case:
        Description of the most favourable plausible outcome.
    neutral_case:
        Description of the most likely / neutral outcome.
    """

    best_case: str
    neutral_case: str

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"best_case": self.best_case, "neutral_case": self.neutral_case}
