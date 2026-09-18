"""``CascadeChainState`` — state threaded across cascade tiers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


@dataclass
class CascadeChainState(PirnOpaqueValue):
    """A cascade's inputs plus the decisions accumulated so far.

    ``CascadeLoop`` reads the request, the tiers, the confidence scorer, the meter and
    the spend-cap policy of a run from this value, not from instance attributes on the
    loop knot. Inputs held on the knot break two contracts: ``step``/``fold`` can then
    only be exercised through a constructor that re-supplies them, not called standalone
    with plain values (knot-design-rules.md Rules 2 and 4), and the state a run records
    in lineage omits what the run was actually driven by. It is also unsafe the moment
    such a loop is wired into a graph that outlives one invocation rather than rebuilt
    inside its pipeline's ``process()``, since the knot object is then shared by every
    run of that graph (PIR-873).

    Attributes:
        request: The prompt every tier attempts.
        tiers: The ordered tiers, attempted front to back.
        confidence: Scores a tier's answer; a score below the tier's
            ``min_confidence`` escalates.
        meter: The budget meter each attempted tier's cost is spent against,
            or ``None`` for an unmetered cascade.
        spend_cap_policy: What to do when the next tier would breach the cap.
        attempted: The names of the tiers attempted so far, in order.
        decisions: One human-readable line per tier processed.
        best_value: The highest-confidence answer seen that was not accepted.
        best_tier: The tier that produced ``best_value``.
        best_confidence: ``best_value``'s score.
        accepted_outcome: The accepted tier's outcome, once one is accepted.
        locked: Whether the cascade has stopped (accepted or downshifted).
    """

    request: str
    tiers: tuple[CascadeTier, ...]
    confidence: Callable[[Any], Awaitable[float]]
    meter: Any
    spend_cap_policy: SpendCapPolicy
    attempted: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    best_value: Any = None
    best_tier: str | None = None
    best_confidence: float | None = None
    accepted_outcome: CascadeOutcome | None = None
    locked: bool = False

    def next_tier(self) -> CascadeTier | None:
        """The tier the next attempt runs, or ``None`` once locked or exhausted."""
        index = len(self.decisions)
        if self.locked or index >= len(self.tiers):
            return None
        return self.tiers[index]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "tiers": [tier.name for tier in self.tiers],
            "metered": self.meter is not None,
            "spend_cap_policy": str(self.spend_cap_policy),
            "attempted": list(self.attempted),
            "decisions": list(self.decisions),
            "best_tier": self.best_tier,
            "best_confidence": self.best_confidence,
            "accepted": self.accepted_outcome is not None,
            "locked": self.locked,
        }
