"""``RateLimitSignal`` — a provider-neutral throttle signal for the batch engine."""

from __future__ import annotations


class RateLimitSignal(Exception):
    """Raised by a per-item agent callable to signal an upstream rate limit.

    The batch engine treats this distinctly from an ordinary item failure: it is
    the provider-neutral way for a ``run_item`` adapter to report a 429-style
    "slow down" so the engine can (a) scale its adaptive concurrency down and
    (b) honour an upstream ``Retry-After`` by pausing the shared F21 token
    bucket. It carries no provider-specific detail — an adapter translates
    whatever its backend raised into this one signal.

    Parameters
    ----------
    retry_after:
        Seconds the upstream asked the caller to wait before retrying, or
        ``None`` when no hint was given. Must be non-negative when present.
    message:
        Optional human-readable detail carried into the item's error text.
    """

    def __init__(self, retry_after: float | None = None, message: str | None = None) -> None:
        if retry_after is not None and (
            isinstance(retry_after, bool)
            or not isinstance(retry_after, (int, float))
            or retry_after < 0
        ):
            raise ValueError(
                f"RateLimitSignal: retry_after must be a non-negative number or None, "
                f"got {retry_after!r}"
            )
        self.retry_after = retry_after
        super().__init__(message or "rate limited by upstream")
