"""``FrozenClock`` — a deterministic :class:`Clock` fixed at an epoch instant."""

from __future__ import annotations

from datetime import UTC, datetime

from pirn_agents.determinism.clock import Clock


class FrozenClock(Clock):
    """A clock frozen at ``epoch`` that only moves when explicitly advanced.

    Time reads are reproducible: :meth:`now` returns ``epoch`` plus the total
    advanced offset, and :meth:`monotonic` returns that offset in seconds. A run
    that threads a frozen clock produces byte-identical timestamps every replay.
    """

    def __init__(self, *, epoch: datetime | None = None) -> None:
        """Initialise the clock at ``epoch`` (defaults to the Unix epoch, UTC).

        Raises:
            TypeError: If ``epoch`` is given but is not a ``datetime``.
        """
        if epoch is not None and not isinstance(epoch, datetime):
            raise TypeError(f"FrozenClock: epoch must be a datetime, got {type(epoch).__name__}")
        base = epoch if epoch is not None else datetime(1970, 1, 1, tzinfo=UTC)
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)
        self._epoch = base
        self._offset_seconds = 0.0

    def now(self) -> datetime:
        """Return ``epoch`` shifted by the total advanced offset."""
        return self._epoch.fromtimestamp(self._epoch.timestamp() + self._offset_seconds, tz=UTC)

    def monotonic(self) -> float:
        """Return the total advanced offset in seconds (0.0 until advanced)."""
        return self._offset_seconds

    def advance(self, seconds: float) -> None:
        """Move the frozen clock forward by ``seconds``.

        Raises:
            ValueError: If ``seconds`` is negative (the clock never runs back).
        """
        if seconds < 0:
            raise ValueError(f"FrozenClock.advance: seconds must be >= 0, got {seconds}")
        self._offset_seconds += float(seconds)
