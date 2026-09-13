"""Raised — as an ``Err`` — when a knot's attempt outlives ``KnotConfig.timeout``."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class KnotTimeoutError(PirnError):
    """A dispatch of a knot did not finish within its configured timeout.

    The engine cancels the attempt and records this as the knot's ``Err``;
    it is never raised out of ``tapestry.run()``.  Under ``KnotConfig.retry``
    a timed-out attempt is retryable like any other failure.

    Attributes:
        knot_id: The knot whose attempt timed out.
        timeout: The limit that was exceeded, in seconds.
    """

    def __init__(self, knot_id: str, timeout: float) -> None:
        super().__init__(f"knot {knot_id!r} did not finish within {timeout}s")
        self.knot_id = knot_id
        self.timeout = timeout
