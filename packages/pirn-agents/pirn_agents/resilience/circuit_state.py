"""``CircuitState`` — the three states of a circuit breaker."""

from __future__ import annotations

from enum import Enum


class CircuitState(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Which phase of the closed/open/half-open cycle a breaker is in.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    CLOSED:
        Normal operation — calls pass through and failures are counted.
    OPEN:
        The endpoint is considered dead; calls fail fast without touching the
        network until the cooldown elapses.
    HALF_OPEN:
        A trial phase entered after cooldown — a bounded number of probe calls
        are allowed; enough successes close the breaker, a single failure
        re-opens it.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
