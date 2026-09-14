"""``CascadeChainState`` — state threaded across cascade tiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome


@dataclass
class CascadeChainState:
    """State threaded across cascade tiers."""

    attempted: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    best_value: Any = None
    best_tier: str | None = None
    best_confidence: float | None = None
    accepted_outcome: CascadeOutcome | None = None
    locked: bool = False
