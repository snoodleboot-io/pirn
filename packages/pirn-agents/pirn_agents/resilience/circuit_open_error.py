"""``CircuitOpenError`` — raised when a call is rejected by an open breaker."""

from __future__ import annotations


class CircuitOpenError(RuntimeError):
    """Raised when a call is short-circuited because the breaker is OPEN.

    Raised *before* any network call is attempted, so a dead endpoint fails
    fast instead of stalling. Carries the ``endpoint`` whose breaker is open and
    the monotonic ``retry_at`` timestamp at which a HALF_OPEN trial becomes
    permissible, for diagnostics and backoff scheduling.

    Attributes
    ----------
    endpoint:
        Stable identity of the endpoint/key whose breaker is open.
    retry_at:
        Monotonic-clock timestamp (same reference as the breaker's clock) at or
        after which a trial call will be allowed, or ``None`` if unknown.
    """

    def __init__(self, endpoint: str, retry_at: float | None = None) -> None:
        self.endpoint = endpoint
        self.retry_at = retry_at
        suffix = "" if retry_at is None else f" (retry at {retry_at:.3f})"
        super().__init__(f"circuit breaker open for endpoint {endpoint!r}{suffix}")
