"""``SingleFlight`` — coalesce concurrent identical in-flight calls into one.

When several callers request the same work (same content-hash key) at the same
time, only the *first* actually runs the factory; the rest attach to the same
in-flight :class:`asyncio.Future` and share its outcome — value or exception —
the moment it resolves. This removes the duplicate provider round-trips a naive
"every caller calls the provider" path pays for a thundering herd of identical
LLM/embedding requests.

A single caller sees no behavioural change: the key is created, awaited, and
removed, so the very next call recomputes (this is coalescing of *concurrent*
work, not a result cache — pair it with a
:class:`~pirn_agents.caching.result_cache.ResultCache` for persistence). The
mechanism is pure ``asyncio`` and provider-neutral; no vendor SDK is imported.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


def _consume_outcome(future: asyncio.Future[Any]) -> None:
    """Retrieve a resolved future's outcome so a no-waiter result never warns."""
    if not future.cancelled():
        future.exception()  # marks the exception (if any) retrieved; None for a result


class SingleFlight:
    """De-duplicate concurrent identical async calls by key (single-flight)."""

    def __init__(self) -> None:
        """Create a coalescer with no in-flight calls."""
        self._in_flight: dict[str, asyncio.Future[Any]] = {}
        self.coalesced = 0

    def __len__(self) -> int:
        return len(self._in_flight)

    async def run(self, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
        """Run ``factory`` once per ``key`` while a call is in flight, sharing the result.

        The first caller for a key starts the work and drives it to completion;
        callers arriving while it is still running await the same future and
        receive the identical result (or the identical raised exception). Once
        the work resolves the key is cleared, so a later call runs afresh.

        Args:
            key: The coalescing key — identical concurrent work must share it
                (typically a content address of the request).
            factory: Async factory producing the value; invoked at most once per
                in-flight generation of ``key``.

        Returns:
            The value produced by the single underlying call.

        Raises:
            Exception: Whatever ``factory`` raises is propagated to every waiter.
        """
        existing = self._in_flight.get(key)
        if existing is not None:
            self.coalesced += 1
            return await existing

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        # The leader re-raises directly, so on the no-waiter error path nothing
        # awaits this future; retrieve its outcome in a done-callback to suppress
        # asyncio's "exception was never retrieved" warning without affecting the
        # value waiters observe when they await it.
        future.add_done_callback(_consume_outcome)
        self._in_flight[key] = future
        try:
            result = await factory()
        except BaseException as exc:  # re-raised after fanning the outcome out to waiters
            if not future.done():
                future.set_exception(exc)
            self._in_flight.pop(key, None)
            raise
        else:
            if not future.done():
                future.set_result(result)
            self._in_flight.pop(key, None)
            return result
