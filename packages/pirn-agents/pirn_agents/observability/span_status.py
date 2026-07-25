"""``SpanStatus`` — terminal disposition of a :class:`Span`."""

from __future__ import annotations

from enum import Enum


class SpanStatus(str, Enum):  # noqa: UP042 - str-mixin form for stable serialisation
    """Outcome of a span.

    Members
    -------
    UNSET:
        The span has not finished yet.
    OK:
        The wrapped operation completed successfully.
    ERROR:
        The wrapped operation raised or otherwise failed.
    """

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"
