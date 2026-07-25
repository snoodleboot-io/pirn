"""``SystemClock`` — the live :class:`Clock` backed by the OS wall/monotonic time."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from pirn_agents.determinism.clock import Clock


class SystemClock(Clock):
    """The production clock: real UTC wall time and the OS monotonic counter.

    This is the single sanctioned place that reads the real clock, so all other
    code can depend on the injectable :class:`Clock` interface and be frozen for
    deterministic runs.
    """

    def now(self) -> datetime:
        """Return the current UTC instant (timezone-aware)."""
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """Return the OS monotonic clock in fractional seconds."""
        return time.monotonic()
