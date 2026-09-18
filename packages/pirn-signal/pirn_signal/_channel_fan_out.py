"""``ChannelFanOut`` — bounded per-channel fan-out inside a knot's ``process()``.

Every multi-channel knot in this package does the same thing: split the sample
array into channels and run one numpy/scipy computation per channel. Written as
``asyncio.gather(*(asyncio.to_thread(worker, channel) for channel in channels))``
that submits one job per channel at once, so a 512-channel EEG or seismic array
queues 512 jobs — each holding its own copy of the channel and its intermediates
— on the event loop's single shared default executor, inside one admission slot
of the engine. The knot's own memory then scales with the channel count rather
than with the parallelism that can actually be used, and every other knot in the
run competes for the same executor behind that queue.

This class runs the same work with a bound: at most one job in flight per
available CPU. The work is CPU-bound array arithmetic, so more concurrent jobs
than CPUs buys no throughput; the bound only removes the pile-up.

Algorithm:
    1. Take a sequence of per-channel calls.
    2. Acquire a semaphore sized at ``min(len(calls), cpu_count)``.
    3. Run each call — on a worker thread for a plain callable, or awaited
       directly for a coroutine factory — and release the slot.
    4. Return the results in the order the calls were given, as
       ``asyncio.gather`` does.

References:
    - asyncio.to_thread and the default executor:
      https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


class ChannelFanOut:
    """Run per-channel work concurrently, bounded by the CPU count."""

    @staticmethod
    def parallelism(call_count: int) -> int:
        """Number of per-channel jobs to keep in flight for ``call_count`` channels.

        Args:
            call_count: Number of channels (or bands) to process.

        Returns:
            At least one, at most one job per available CPU and never more than
            ``call_count``.
        """
        return max(1, min(call_count, os.cpu_count() or 1))

    @staticmethod
    async def gather(calls: Sequence[Callable[[], T]]) -> list[T]:
        """Run each zero-argument call on a worker thread, bounded, preserving order.

        Args:
            calls: One call per channel, typically ``functools.partial`` bindings of a
                static per-channel worker.

        Returns:
            Each call's result, in the order the calls were given.
        """
        semaphore = asyncio.Semaphore(ChannelFanOut.parallelism(len(calls)))
        return list(
            await asyncio.gather(*(ChannelFanOut._run_call(semaphore, call) for call in calls))
        )

    @staticmethod
    async def gather_awaitables(factories: Sequence[Callable[[], Awaitable[T]]]) -> list[T]:
        """Await one coroutine per channel, bounded, preserving order.

        For channel workers that are themselves coroutines (they await more than one
        threaded step), so the bound applies to the whole per-channel pipeline rather
        than to each step separately.

        Args:
            factories: One coroutine factory per channel; each is called once.

        Returns:
            Each coroutine's result, in the order the factories were given.
        """
        semaphore = asyncio.Semaphore(ChannelFanOut.parallelism(len(factories)))
        return list(
            await asyncio.gather(
                *(ChannelFanOut._run_awaitable(semaphore, factory) for factory in factories)
            )
        )

    @staticmethod
    async def _run_call(semaphore: asyncio.Semaphore, call: Callable[[], T]) -> T:
        """Run one call on a worker thread while holding a fan-out slot."""
        async with semaphore:
            return await asyncio.to_thread(call)

    @staticmethod
    async def _run_awaitable(
        semaphore: asyncio.Semaphore, factory: Callable[[], Awaitable[T]]
    ) -> T:
        """Await one channel coroutine while holding a fan-out slot."""
        async with semaphore:
            return await factory()
