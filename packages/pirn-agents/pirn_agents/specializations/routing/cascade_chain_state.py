"""``CascadeChainState`` — state threaded across cascade tiers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome
from pirn_agents.specializations.routing.cascade_tier import CascadeTier


@dataclass
class CascadeChainState:
    """State threaded across cascade tiers."""

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
