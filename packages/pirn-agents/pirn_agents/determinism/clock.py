"""``Clock`` — the injectable time source threaded through a run.

Nothing in a deterministic run may call the wall clock directly (``Date.now`` /
``datetime.now`` / ``time.monotonic``); every time read goes through an injected
:class:`Clock`. Production runs use
:class:`~pirn_agents.determinism.system_clock.SystemClock`; deterministic runs use
:class:`~pirn_agents.determinism.frozen_clock.FrozenClock` so timestamps are
reproducible.
"""

from __future__ import annotations

from datetime import datetime


class Clock:
    """Interface for a time source: a wall-clock instant and a monotonic tick."""

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware :class:`datetime`."""
        raise NotImplementedError(f"{type(self).__name__} must implement now()")

    def monotonic(self) -> float:
        """Return a monotonically non-decreasing tick in fractional seconds."""
        raise NotImplementedError(f"{type(self).__name__} must implement monotonic()")
