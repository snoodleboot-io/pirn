"""Cron-style trigger.

Fires a ``RunRequest`` at fixed intervals or at specific times.  Pure
Python; no external scheduling library required.

Two construction modes:

* ``CronTrigger(every_seconds=300)`` — every N seconds (most common
  for periodic jobs).
* ``CronTrigger(at_times=[...])`` — at specific ``datetime.time``
  values within each day (e.g., daily reports at 09:00 and 17:00).

For full crontab-style expressions ("every Monday at 02:30 except
holidays"), wire in ``croniter`` or ``apscheduler`` and yield through
this trigger's interface.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class CronTrigger(Trigger):
    """Time-based trigger that fires on a fixed interval or at specific times of day.

    Two construction modes are supported:

    * **Interval mode** — ``CronTrigger(every_seconds=300)`` yields a
      ``RunRequest`` immediately on first iteration, then once every
      *N* seconds.
    * **At-times mode** — ``CronTrigger(at_times=[time(9, 0), time(17, 0)])``
      waits until the next matching wall-clock time (UTC) and yields then,
      repeating daily.

    For full crontab expressions, wrap ``croniter`` or ``apscheduler``
    and yield through this trigger's interface.
    """

    def __init__(
        self,
        *,
        every_seconds: float | None = None,
        at_times: list[time] | None = None,
        parameters_factory: Callable[[], dict[str, Any]] | None = None,
        max_runs: int | None = None,
    ) -> None:
        """Initialise the trigger.

        Args:
            every_seconds: Interval between runs in seconds (interval
                mode).  Mutually exclusive with ``at_times``.
            at_times: List of UTC ``datetime.time`` values at which to
                fire each day (at-times mode).  Mutually exclusive with
                ``every_seconds``.
            parameters_factory: Zero-argument callable returning a
                ``dict`` of run parameters.  Called once per emitted
                ``RunRequest``.  Defaults to an empty dict when ``None``.
            max_runs: Stop after this many ``RunRequest``s.  Runs
                indefinitely when ``None``.

        Raises:
            TypeError: If neither or both of ``every_seconds`` and
                ``at_times`` are supplied.
        """
        if every_seconds is None and at_times is None:
            raise TypeError("CronTrigger requires either every_seconds= or at_times=")
        if every_seconds is not None and at_times is not None:
            raise TypeError("CronTrigger: pass either every_seconds= or at_times=, not both")

        self._every_seconds = every_seconds
        self._at_times = sorted(at_times or [])
        self._parameters_factory = parameters_factory
        self._max_runs = max_runs
        self._closed = False

    @property
    def name(self) -> str:
        return "CronTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        """Yield ``RunRequest`` objects according to the configured schedule.

        In interval mode the first request is yielded immediately; in
        at-times mode the generator waits until the next scheduled wall-
        clock time before yielding.  Stops after ``max_runs`` requests
        when set, or when ``close()`` is called.

        Yields:
            One ``RunRequest`` per scheduled fire time.
        """
        emitted = 0
        if self._every_seconds is not None:
            while not self._closed:
                if self._max_runs is not None and emitted >= self._max_runs:
                    return
                yield self._build_request()
                emitted += 1
                await asyncio.sleep(self._every_seconds)
        else:
            # at_times mode.
            while not self._closed:
                if self._max_runs is not None and emitted >= self._max_runs:
                    return
                wait = self._seconds_until_next_at_time()
                await asyncio.sleep(wait)
                yield self._build_request()
                emitted += 1

    def _build_request(self) -> RunRequest:
        """Construct a ``RunRequest`` using the configured parameters factory.

        Returns:
            A new ``RunRequest`` whose ``parameters`` dict is produced by
            ``parameters_factory()``, or an empty dict if no factory was
            configured.
        """
        params: dict[str, Any] = (
            self._parameters_factory() if self._parameters_factory is not None else {}
        )
        return RunRequest(parameters=params)

    def _seconds_until_next_at_time(self) -> float:
        """Return the number of seconds until the next scheduled at-time fires.

        Considers all configured times for today (UTC); if all have
        passed, returns the wait until the first time tomorrow.

        Returns:
            Seconds to sleep before the next fire time.
        """
        now = datetime.now(UTC)
        today = now.date()
        for t in self._at_times:
            candidate = datetime.combine(today, t, tzinfo=UTC)
            if candidate > now:
                return (candidate - now).total_seconds()
        # All today's times have passed; first time tomorrow.
        tomorrow = today + timedelta(days=1)
        candidate = datetime.combine(tomorrow, self._at_times[0], tzinfo=UTC)
        return (candidate - now).total_seconds()

    async def close(self) -> None:
        """Signal the trigger to stop after the current sleep completes."""
        self._closed = True
