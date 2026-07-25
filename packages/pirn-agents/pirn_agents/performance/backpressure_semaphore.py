"""``BackpressureSemaphore`` — bounded concurrency with queue-depth backpressure.

Wraps an :class:`asyncio.Semaphore` sized from a
:class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig` and adds
two things the bare semaphore lacks: a bounded *wait queue* (so an overloaded
call site sheds load with a typed :class:`asyncio.QueueFull` instead of piling
up unbounded waiters) and an optional acquire timeout. Tool executors and
provider call sites acquire a slot via the :meth:`slot` async context manager,
so the concurrency posture lives in one shared config rather than scattered
magic numbers.

By default (``max_queue_depth is None``) excess callers simply queue and back
off on the semaphore — never failing — which is the ADR's "queue rather than
fail" backpressure default.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class BackpressureSemaphore:
    """A concurrency limiter that queues or sheds load per a shared config."""

    def __init__(self, config: ConcurrencyConfig) -> None:
        """Build the limiter from a :class:`ConcurrencyConfig`.

        Raises:
            TypeError: If ``config`` is not a :class:`ConcurrencyConfig`.
        """
        if not isinstance(config, ConcurrencyConfig):
            raise TypeError(
                f"BackpressureSemaphore: config must be a ConcurrencyConfig, "
                f"got {type(config).__name__}"
            )
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._waiting = 0
        self._in_flight = 0

    @property
    def config(self) -> ConcurrencyConfig:
        """The config this limiter was built from."""
        return self._config

    @property
    def in_flight(self) -> int:
        """Number of slots currently held."""
        return self._in_flight

    @property
    def waiting(self) -> int:
        """Number of callers currently blocked waiting for a slot."""
        return self._waiting

    async def acquire(self) -> None:
        """Acquire one slot, honouring the queue bound and acquire timeout.

        Raises:
            asyncio.QueueFull: If ``max_queue_depth`` is set and the wait queue
                is already full — the backpressure signal to shed load.
            TimeoutError: If ``acquire_timeout`` elapses before a slot frees.
        """
        depth = self._config.max_queue_depth
        if depth is not None and self._waiting >= depth:
            raise asyncio.QueueFull(
                f"BackpressureSemaphore: wait queue full (max_queue_depth={depth})"
            )
        self._waiting += 1
        try:
            timeout = self._config.acquire_timeout
            if timeout is not None:
                async with asyncio.timeout(timeout):
                    await self._semaphore.acquire()
            else:
                await self._semaphore.acquire()
        finally:
            self._waiting -= 1
        self._in_flight += 1

    def release(self) -> None:
        """Release one previously acquired slot."""
        self._in_flight -= 1
        self._semaphore.release()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Acquire a slot for the duration of the ``async with`` block.

        The slot is always released, even if the body raises, so a failing
        operation never leaks concurrency capacity.
        """
        await self.acquire()
        try:
            yield
        finally:
            self.release()
