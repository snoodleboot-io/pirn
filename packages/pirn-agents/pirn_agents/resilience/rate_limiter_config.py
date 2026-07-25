"""``RateLimiterConfig`` — refill rate and burst capacity of a token bucket."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RateLimiterConfig(PirnOpaqueValue):
    """How fast a token bucket refills and how large a burst it tolerates.

    A frozen value (not a module constant) so every provider/key limiter is
    built from the *same* knob object rather than re-inventing rate literals.

    Attributes
    ----------
    refill_rate:
        Tokens replenished per second. Must be > 0.
    capacity:
        Maximum tokens the bucket holds — the largest instantaneous burst. Must
        be > 0. Defaults to ``refill_rate`` semantics only when set explicitly;
        there is no implicit coupling.
    """

    refill_rate: float
    capacity: float

    def __post_init__(self) -> None:
        """Validate the rate and capacity."""
        if (
            isinstance(self.refill_rate, bool)
            or not isinstance(self.refill_rate, (int, float))
            or self.refill_rate <= 0
        ):
            raise ValueError(
                f"RateLimiterConfig: refill_rate must be a positive number, "
                f"got {self.refill_rate!r}"
            )
        if (
            isinstance(self.capacity, bool)
            or not isinstance(self.capacity, (int, float))
            or self.capacity <= 0
        ):
            raise ValueError(
                f"RateLimiterConfig: capacity must be a positive number, got {self.capacity!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"refill_rate": self.refill_rate, "capacity": self.capacity}
