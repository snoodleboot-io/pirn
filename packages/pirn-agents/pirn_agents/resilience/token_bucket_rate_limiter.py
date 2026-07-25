"""``TokenBucketRateLimiter`` — a shared async token bucket.

One limiter is shared across all concurrent callers for a given provider/key.
Tokens refill continuously at :attr:`RateLimiterConfig.refill_rate` up to
:attr:`RateLimiterConfig.capacity`; :meth:`acquire` consumes tokens, waiting
(cooperatively — it ``await``\\ s a sleep rather than busy-polling) until enough
have accrued. An upstream ``Retry-After`` is honoured via :meth:`pause_for`,
which floors acquisition until the pause elapses.

Acquisition is serialised behind an :class:`asyncio.Lock`, so concurrent callers
draw from one shared bucket in FIFO order rather than each keeping a private
count. The clock and sleep are injected (defaulting to :func:`time.monotonic`
and :func:`asyncio.sleep`) so tests drive refills deterministically without real
elapsed time.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from pirn_agents.resilience.rate_limiter_config import RateLimiterConfig


class TokenBucketRateLimiter:
    """A cooperative, shared token bucket for per-provider/key rate limiting."""

    def __init__(
        self,
        config: RateLimiterConfig,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Build the limiter, starting full at ``capacity``.

        Args:
            config: Refill rate and burst capacity.
            clock: Zero-arg monotonic clock; defaults to :func:`time.monotonic`.
            sleep: Async sleep used while waiting; defaults to
                :func:`asyncio.sleep`. Injected in tests so a fake sleep can
                advance a manual clock deterministically.

        Raises:
            TypeError: If ``config`` is not a :class:`RateLimiterConfig`.
        """
        if not isinstance(config, RateLimiterConfig):
            raise TypeError(
                f"TokenBucketRateLimiter: config must be a RateLimiterConfig, "
                f"got {type(config).__name__}"
            )
        self._config = config
        self._clock = clock if clock is not None else time.monotonic
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._tokens = float(config.capacity)
        self._updated_at = self._clock()
        self._paused_until = 0.0
        self._lock = asyncio.Lock()

    @property
    def config(self) -> RateLimiterConfig:
        """The config this limiter was built from."""
        return self._config

    @property
    def available_tokens(self) -> float:
        """The token count as of the last refill (no refill is applied on read)."""
        return self._tokens

    def pause_for(self, seconds: float) -> None:
        """Floor acquisition for ``seconds`` from now (honours ``Retry-After``).

        Extends any existing pause rather than shortening it, so overlapping
        ``Retry-After`` hints compose to the latest deadline.

        Raises:
            ValueError: If ``seconds`` is negative.
        """
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            raise ValueError(
                f"TokenBucketRateLimiter: pause seconds must be a non-negative number, "
                f"got {seconds!r}"
            )
        self._paused_until = max(self._paused_until, self._clock() + seconds)

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._updated_at
        if elapsed > 0:
            self._tokens = min(
                float(self._config.capacity),
                self._tokens + elapsed * self._config.refill_rate,
            )
            self._updated_at = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire ``tokens``, waiting cooperatively until they are available.

        Args:
            tokens: How many tokens the call costs. Must be > 0 and not exceed
                the bucket ``capacity`` (an un-satisfiable request).

        Raises:
            ValueError: If ``tokens`` is non-positive or exceeds capacity.
        """
        if isinstance(tokens, bool) or not isinstance(tokens, (int, float)) or tokens <= 0:
            raise ValueError(
                f"TokenBucketRateLimiter: tokens must be a positive number, got {tokens!r}"
            )
        if tokens > self._config.capacity:
            raise ValueError(
                f"TokenBucketRateLimiter: cannot acquire {tokens} tokens; "
                f"exceeds capacity {self._config.capacity}"
            )
        async with self._lock:
            while True:
                self._refill()
                now = self._clock()
                if now < self._paused_until:
                    await self._sleep(self._paused_until - now)
                    continue
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                await self._sleep(deficit / self._config.refill_rate)
