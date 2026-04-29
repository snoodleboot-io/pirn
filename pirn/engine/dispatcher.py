"""Dispatchers — where work runs.

A ``Dispatcher`` answers: given a knot and its already-resolved inputs,
produce its ``Result``.

Phase 2 ships:
* ``LocalDispatcher`` — runs in the current event loop.
* ``ThreadDispatcher`` — offloads to a global thread pool.  Useful for
  CPU-bound or sync-heavy knots that would otherwise block the loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, runtime_checkable

from pirn.core.knot import Knot
from pirn.core.result import Result


@runtime_checkable
class Dispatcher(Protocol):
    """Run a knot somewhere and return its ``Result``."""

    @property
    def name(self) -> str: ...

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]: ...


class LocalDispatcher:
    """Run knots in the current event loop.

    Trivial: ``await knot(inputs)``.  ``Knot.__call__`` already catches
    exceptions and wraps results, so this dispatcher does nothing else.
    """

    @property
    def name(self) -> str:
        return "LocalDispatcher"

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        return await knot(inputs)


class ThreadDispatcher:
    """Run knots in a global thread pool.

    For CPU-bound or blocking-IO knots that should not stall the event
    loop.  The pool is shared across all knots dispatched through this
    instance.

    Note: ``Knot.__call__`` is async, so we can't simply submit it to a
    thread pool — we need to run a fresh event loop inside the worker
    thread.  ``asyncio.run`` does that; the cost is per-knot and small.
    For knots that are themselves sync (``@knot`` on a sync function),
    this is exactly the right shape.
    """

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
        # Submit the knot's __call__ to the pool by wrapping it in a sync
        # helper that spins a fresh event loop.  The helper returns the
        # Result directly.
        return await loop.run_in_executor(self._executor, _run_in_thread, knot, dict(inputs))

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying pool.  Safe to call multiple times."""
        self._executor.shutdown(wait=wait)


def _run_in_thread(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
    """Worker-thread entry point.  Runs ``knot(inputs)`` in a fresh loop.

    Each call constructs a new event loop because the worker thread
    doesn't have one.  ``asyncio.run`` handles setup and teardown.
    """
    return asyncio.run(knot(inputs))
