"""``CascadeTier`` — one rung of a cost-ordered model cascade."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CascadeTier(PirnOpaqueValue):
    """A single model tier the cascade may try, cheapest listed first.

    Attributes
    ----------
    name:
        Stable identifier for the tier, surfaced in the observable
        :class:`~pirn_agents.specializations.routing.cascade_outcome.CascadeOutcome`.
    invoke:
        Async callable mapping the request to this tier's model output — the
        provider seam, so the cascade names no vendor.
    min_confidence:
        Confidence floor this tier's output must clear to be accepted; below it
        the cascade escalates. ``0.0`` (the default) means always accept.
    estimated_cost:
        Estimated cost of invoking this tier, accrued into a
        :class:`~pirn_agents.performance.run_budget_meter.RunBudgetMeter` when one
        is supplied. Defaults to ``0.0``.
    """

    name: str
    invoke: Callable[[Any], Awaitable[Any]]
    min_confidence: float = 0.0
    estimated_cost: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("CascadeTier: name must be a non-empty str")
        if not callable(self.invoke):
            raise TypeError("CascadeTier: invoke must be an async callable")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(
                f"CascadeTier: min_confidence must be in [0, 1], got {self.min_confidence!r}"
            )
        if self.estimated_cost < 0:
            raise ValueError(
                f"CascadeTier: estimated_cost must be non-negative, got {self.estimated_cost!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "invoke": repr(self.invoke),
            "min_confidence": self.min_confidence,
            "estimated_cost": self.estimated_cost,
        }
