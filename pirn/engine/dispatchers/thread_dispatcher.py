from __future__ import annotations

import asyncio
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
        return await loop.run_in_executor(
            self._executor, ThreadDispatcher.__run_in_thread, knot, dict(inputs)
        )

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying pool.  Safe to call multiple times."""
        self._executor.shutdown(wait=wait)
