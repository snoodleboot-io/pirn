"""``LatsFrame`` — lineage metadata for a :class:`LatsResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LatsFrame(PirnOpaqueValue):
    """Run-level facts for a budget-bounded LATS search.

    The frame half of the ``Payload[LatsFrame, tuple[str, ...]]`` split
    (PIR-868).

    Attributes
    ----------
    best_value:
        The value of the best trajectory found.
    nodes_expanded:
        How many nodes were expanded before the search stopped.
    budget_exhausted:
        Whether the search stopped because the node/time budget was hit (as
        opposed to exhausting the frontier).
    """

    best_value: float
    nodes_expanded: int
    budget_exhausted: bool

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "best_value": self.best_value,
            "nodes_expanded": self.nodes_expanded,
            "budget_exhausted": self.budget_exhausted,
        }
