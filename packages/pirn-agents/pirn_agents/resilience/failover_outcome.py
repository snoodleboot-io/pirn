"""``FailoverOutcome`` — why a failover candidate was skipped, failed, or won."""

from __future__ import annotations

from enum import Enum


class FailoverOutcome(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """The disposition of one candidate in a :class:`FailoverChain` run.

    String-valued for stable, human-readable trace serialisation independent of
    enum ordering.

    Members
    -------
    SUCCESS:
        The candidate ran and returned a value; the chain stops here.
    ERROR:
        The candidate raised a non-timeout exception; the chain moves on.
    TIMEOUT:
        The candidate exceeded its per-candidate timeout; the chain moves on.
    CIRCUIT_OPEN:
        The candidate was skipped because its circuit breaker was open; no call
        was attempted.
    """

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"
