"""``IntervalTrigger`` — a scheduled batch trigger (F28-S5 / PIR-584).

Fires on a schedule: by default every ``interval`` seconds, optionally bounded by
``max_fires``. The schedule is pluggable through ``delay_fn`` — a
``Callable[[int], float]`` mapping the next 1-based fire ordinal to the seconds to
wait before it — which is the seam an external **cron** backend fills (a croniter/
APScheduler-derived "seconds until next cron instant" function drops straight in)
without this module importing any scheduler. The async ``sleep`` is injected so
tests advance the schedule deterministically with no wall-clock wait.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from pirn_agents.batch.batch_trigger import BatchTrigger


class IntervalTrigger(BatchTrigger):
    """Fire on a fixed interval or an injected per-fire delay schedule."""

    def __init__(
        self,
        *,
        interval: float | None = None,
        delay_fn: Callable[[int], float] | None = None,
        max_fires: int | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Configure the schedule.

        Args:
            interval: Constant seconds to wait before each fire. Mutually
                exclusive with ``delay_fn``; exactly one must be given.
            delay_fn: Maps the next 1-based fire ordinal to the seconds to wait
                before it — the cron seam. Mutually exclusive with ``interval``.
            max_fires: Stop after this many fires; ``None`` runs unbounded.
            sleep: Async sleep used between fires; injected in tests. Defaults to
                :func:`asyncio.sleep`.

        Raises:
            ValueError: If neither or both of ``interval``/``delay_fn`` are given,
                ``interval`` is negative, or ``max_fires`` < 1.
        """
        if (interval is None) == (delay_fn is None):
            raise ValueError("IntervalTrigger: give exactly one of interval or delay_fn")
        if interval is not None and interval < 0:
            raise ValueError(f"IntervalTrigger: interval must be >= 0, got {interval!r}")
        if max_fires is not None and (isinstance(max_fires, bool) or max_fires < 1):
            raise ValueError(f"IntervalTrigger: max_fires must be an int >= 1, got {max_fires!r}")
        self._interval = interval
        self._delay_fn = delay_fn
        self._max_fires = max_fires
        self._sleep = sleep if sleep is not None else asyncio.sleep

    async def fires(self) -> AsyncIterator[int]:
        """Yield a 1-based ordinal per fire, waiting the scheduled delay first."""
        ordinal = 0
        while self._max_fires is None or ordinal < self._max_fires:
            ordinal += 1
            delay = self._delay_fn(ordinal) if self._delay_fn is not None else self._interval
            if delay and delay > 0:
                await self._sleep(delay)
            yield ordinal
