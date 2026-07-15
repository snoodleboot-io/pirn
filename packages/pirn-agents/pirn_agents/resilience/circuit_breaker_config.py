"""``CircuitBreakerConfig`` — thresholds governing a breaker's transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class CircuitBreakerConfig(PirnOpaqueValue):
    """Tuning knobs for one circuit breaker's state machine.

    A frozen value (not a module constant) so every endpoint's breaker consumes
    the *same* knob object rather than re-inventing threshold literals. The
    field defaults are a sensible out-of-the-box posture; override per knot
    config.

    Attributes
    ----------
    failure_threshold:
        Consecutive failures in the CLOSED state that trip the breaker OPEN.
        Must be >= 1. Defaults to 5.
    cooldown_seconds:
        How long the breaker stays OPEN before allowing a HALF_OPEN trial, in
        seconds. Must be > 0. Defaults to 30.0.
    success_threshold:
        Consecutive trial successes in the HALF_OPEN state required to close the
        breaker. Must be >= 1. Defaults to 1.
    """

    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    success_threshold: int = 1

    def __post_init__(self) -> None:
        """Validate the thresholds and cooldown."""
        if (
            isinstance(self.failure_threshold, bool)
            or not isinstance(self.failure_threshold, int)
            or self.failure_threshold < 1
        ):
            raise ValueError(
                f"CircuitBreakerConfig: failure_threshold must be an int >= 1, "
                f"got {self.failure_threshold!r}"
            )
        if (
            isinstance(self.success_threshold, bool)
            or not isinstance(self.success_threshold, int)
            or self.success_threshold < 1
        ):
            raise ValueError(
                f"CircuitBreakerConfig: success_threshold must be an int >= 1, "
                f"got {self.success_threshold!r}"
            )
        if (
            isinstance(self.cooldown_seconds, bool)
            or not isinstance(self.cooldown_seconds, (int, float))
            or self.cooldown_seconds <= 0
        ):
            raise ValueError(
                f"CircuitBreakerConfig: cooldown_seconds must be a positive number, "
                f"got {self.cooldown_seconds!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "success_threshold": self.success_threshold,
        }
