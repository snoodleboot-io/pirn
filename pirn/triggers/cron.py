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
    """Time-based trigger."""

    def __init__(
        self,
        *,
        every_seconds: float | None = None,
        at_times: list[time] | None = None,
        parameters_factory: Callable[[], dict[str, Any]] | None = None,
        max_runs: int | None = None,
    ) -> None:
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
        params: dict[str, Any] = (
            self._parameters_factory() if self._parameters_factory is not None else {}
        )
        return RunRequest(parameters=params)

    def _seconds_until_next_at_time(self) -> float:
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
        self._closed = True
