"""``Bulkhead`` — isolate concurrency into one bounded pool per backend.

Each backend key gets its own
:class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`,
built lazily from a :class:`BulkheadConfig`. Because the pools are independent,
saturating one slow backend's pool only makes *its* callers queue — calls to
other backends keep flowing, so one bad backend can't exhaust a single global
semaphore and starve the rest (the bulkhead pattern). Callers acquire a slot for
a backend via the :meth:`slot` async context manager.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pirn_agents.performance.backpressure_semaphore import BackpressureSemaphore
from pirn_agents.resilience.bulkhead_config import BulkheadConfig


class Bulkhead:
    """Per-backend isolated concurrency pools, created on first use."""

    def __init__(self, config: BulkheadConfig | None = None) -> None:
        """Build the bulkhead.

        Args:
            config: Per-backend pool sizing; defaults to a stock
                :class:`BulkheadConfig` (one default pool for every backend).

        Raises:
            TypeError: If ``config`` is not a :class:`BulkheadConfig`.
        """
        resolved = config if config is not None else BulkheadConfig()
        if not isinstance(resolved, BulkheadConfig):
            raise TypeError(
                f"Bulkhead: config must be a BulkheadConfig or None, got {type(resolved).__name__}"
            )
        self._config = resolved
        self._pools: dict[str, BackpressureSemaphore] = {}

    def _pool(self, backend: str) -> BackpressureSemaphore:
        pool = self._pools.get(backend)
        if pool is None:
            pool = BackpressureSemaphore(self._config.for_backend(backend))
            self._pools[backend] = pool
        return pool

    def backends(self) -> tuple[str, ...]:
        """The backend keys that currently have a live pool."""
        return tuple(self._pools)

    def in_flight(self, backend: str) -> int:
        """Slots currently held for ``backend`` (0 if it has no pool yet)."""
        pool = self._pools.get(backend)
        return 0 if pool is None else pool.in_flight

    def waiting(self, backend: str) -> int:
        """Callers currently waiting for a slot in ``backend``'s pool."""
        pool = self._pools.get(backend)
        return 0 if pool is None else pool.waiting

    @asynccontextmanager
    async def slot(self, backend: str) -> AsyncIterator[None]:
        """Hold one slot in ``backend``'s isolated pool for the block's duration.

        Delegates to that backend's
        :class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`,
        so its bound, queue-depth backpressure, and acquire timeout all apply —
        independently of every other backend's pool.

        Raises:
            asyncio.QueueFull: If the backend's wait queue is bounded and full.
            TimeoutError: If the backend's acquire timeout elapses.
        """
        async with self._pool(backend).slot():
            yield
