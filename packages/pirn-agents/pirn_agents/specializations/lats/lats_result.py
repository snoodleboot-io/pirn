"""``LatsResult`` — the typed outcome of a budgeted LATS search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LatsResult(PirnOpaqueValue):
    """Outcome of a budget-bounded LATS search.

    Attributes
    ----------
    best_trajectory:
        The highest-value action trajectory found within budget.
    best_value:
        The value of ``best_trajectory``.
    nodes_expanded:
        How many nodes were expanded before the search stopped.
    budget_exhausted:
        Whether the search stopped because the node/time budget was hit (as
        opposed to exhausting the frontier).
    """

    best_trajectory: tuple[str, ...]
    best_value: float
    nodes_expanded: int
    budget_exhausted: bool

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "best_trajectory": list(self.best_trajectory),
            "best_value": self.best_value,
            "nodes_expanded": self.nodes_expanded,
            "budget_exhausted": self.budget_exhausted,
        }
