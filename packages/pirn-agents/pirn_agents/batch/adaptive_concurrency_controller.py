"""``AdaptiveConcurrencyController`` — AIMD concurrency control for a batch.

An additive-increase / multiplicative-decrease (AIMD) governor for the number of
in-flight items a :class:`~pirn_agents.batch.map_agent.MapAgent` dispatches. It
complements the F21 :class:`~pirn_agents.resilience.token_bucket_rate_limiter.TokenBucketRateLimiter`
(which paces *requests* against a quota): this governs *parallelism* so the batch
backs off the moment a provider starts throttling and creeps back up while calls
are succeeding, converging on the largest concurrency the quota tolerates.

The math is deterministic and time-free — every transition is driven by observed
success/throttle events, never a wall clock — so tests assert exact limits.
"""

from __future__ import annotations


class AdaptiveConcurrencyController:
    """A time-free AIMD governor over a batch's in-flight item limit."""

    def __init__(
        self,
        *,
        min_limit: int = 1,
        max_limit: int = 8,
        initial: int | None = None,
        increase: float = 1.0,
        decrease_factor: float = 0.5,
    ) -> None:
        """Build the controller.

        Args:
            min_limit: Floor the limit never drops below. Must be >= 1.
            max_limit: Ceiling the limit never climbs above. Must be >= min.
            initial: Starting limit; defaults to ``max_limit`` (optimistic start,
                backing off on the first throttle).
            increase: Additive step added per success. Must be > 0.
            decrease_factor: Multiplier applied on a throttle (0 < f < 1).

        Raises:
            ValueError: If any bound is out of range.
        """
        if isinstance(min_limit, bool) or not isinstance(min_limit, int) or min_limit < 1:
            raise ValueError(
                f"AdaptiveConcurrencyController: min_limit must be >= 1, got {min_limit!r}"
            )
        if isinstance(max_limit, bool) or not isinstance(max_limit, int) or max_limit < min_limit:
            raise ValueError(
                f"AdaptiveConcurrencyController: max_limit must be >= min_limit, got {max_limit!r}"
            )
        if isinstance(increase, bool) or not isinstance(increase, (int, float)) or increase <= 0:
            raise ValueError(
                f"AdaptiveConcurrencyController: increase must be > 0, got {increase!r}"
            )
        if (
            isinstance(decrease_factor, bool)
            or not isinstance(decrease_factor, (int, float))
            or not 0 < decrease_factor < 1
        ):
            raise ValueError(
                f"AdaptiveConcurrencyController: decrease_factor must be in (0, 1), "
                f"got {decrease_factor!r}"
            )
        start = max_limit if initial is None else initial
        if start < min_limit or start > max_limit:
            raise ValueError(
                f"AdaptiveConcurrencyController: initial must be within "
                f"[{min_limit}, {max_limit}], got {start}"
            )
        self._min = min_limit
        self._max = max_limit
        self._increase = float(increase)
        self._decrease = float(decrease_factor)
        self._limit = float(start)

    def limit(self) -> int:
        """The current integer concurrency limit, clamped to ``[min, max]``."""
        return max(self._min, min(self._max, int(self._limit)))

    def on_success(self) -> None:
        """Record a successful item — additively increase toward ``max_limit``."""
        self._limit = min(float(self._max), self._limit + self._increase)

    def on_throttle(self) -> None:
        """Record a throttle — multiplicatively decrease toward ``min_limit``."""
        self._limit = max(float(self._min), self._limit * self._decrease)
