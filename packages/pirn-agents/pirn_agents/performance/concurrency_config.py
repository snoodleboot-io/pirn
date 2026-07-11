"""``ConcurrencyConfig`` — shared bounded-concurrency + backpressure settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ConcurrencyConfig(PirnOpaqueValue):
    """One place to declare how many things may run at once and how they queue.

    A frozen value (not a module constant) so tool executors, provider call
    sites, and dispatchers all consume the *same* knob object rather than
    re-inventing an ``asyncio.Semaphore(8)`` each. The field defaults are the
    sensible out-of-the-box backpressure posture; override per knot config.

    Attributes
    ----------
    max_concurrency:
        Maximum simultaneously in-flight operations (semaphore bound). Must be
        >= 1. Defaults to 8, matching the executor's historical default.
    max_queue_depth:
        Maximum number of callers allowed to *wait* for a slot at once. ``None``
        (the default) means an unbounded wait queue — excess callers queue and
        back off rather than fail. A concrete bound turns overflow into a typed
        :class:`asyncio.QueueFull` for hard backpressure.
    acquire_timeout:
        Seconds a caller may wait for a slot before giving up, or ``None`` for
        no timeout.
    """

    max_concurrency: int = 8
    max_queue_depth: int | None = None
    acquire_timeout: float | None = None

    def __post_init__(self) -> None:
        """Validate the bound and optional backpressure knobs."""
        if (
            isinstance(self.max_concurrency, bool)
            or not isinstance(self.max_concurrency, int)
            or self.max_concurrency < 1
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_concurrency must be an int >= 1, "
                f"got {self.max_concurrency!r}"
            )
        depth = self.max_queue_depth
        if depth is not None and (
            isinstance(depth, bool) or not isinstance(depth, int) or depth < 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: max_queue_depth must be a non-negative int or None, "
                f"got {depth!r}"
            )
        timeout = self.acquire_timeout
        if timeout is not None and (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
        ):
            raise ValueError(
                f"ConcurrencyConfig: acquire_timeout must be a positive number or None, "
                f"got {timeout!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "max_concurrency": self.max_concurrency,
            "max_queue_depth": self.max_queue_depth,
            "acquire_timeout": self.acquire_timeout,
        }
