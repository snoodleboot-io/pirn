from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from pirn.engine.dispatchers.dispatcher import Dispatcher

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.result import Result


class ThreadDispatcher(Dispatcher):
    """Run knots in a global thread pool.

    For CPU-bound or blocking-IO knots that should not stall the event
    loop.  asyncio.run spins a fresh event loop per knot inside the
    worker thread — cost is per-knot and small.

    The dispatched knot runs under a **copy of the caller's context**, so the
    contextvars the engine relies on — ``_current_history``, ``_current_run_id``
    — survive the thread hop.  Without that, a knot that starts an inner run on
    a worker thread cannot see the store the outer run is writing to: the inner
    run is recorded nowhere and is orphaned from its parent.  See PIR-767.

    This is available only because the hop is in-process.  A dispatcher that
    crosses a **process** boundary (Ray, Dask, Celery) cannot propagate
    contextvars — the target interpreter has its own, and the values here are
    live objects rather than anything serialisable.  Knots that depend on
    ambient run context must not be scheduled onto those backends.
    """

    @staticmethod
    def __run_in_thread(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
        return asyncio.run(knot(inputs))

    def __init__(self, max_workers: int | None = None) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pirn-thread",
        )

    @property
    def name(self) -> str:
        return "ThreadDispatcher"

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        loop = asyncio.get_running_loop()
        # `run_in_executor` does not carry the ambient context across the hop,
        # so run the callable inside a copy of it. `asyncio.to_thread` would
        # copy the context for us but always uses the *default* executor, which
        # would silently discard this dispatcher's own pool — and with it
        # `max_workers` and `shutdown()`.
        context = contextvars.copy_context()
        payload = dict(inputs)

        def _run_with_context() -> Result[Any]:
            return context.run(ThreadDispatcher.__run_in_thread, knot, payload)

        return await loop.run_in_executor(self._executor, _run_with_context)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying pool.  Safe to call multiple times."""
        self._executor.shutdown(wait=wait)
