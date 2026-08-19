"""Deterministic stub doubles for the F28 batch-engine tests.

No vendor SDK, no real elapsed time: every double is scripted so the batch
semantics (isolation, ordering, concurrency, backpressure, resume) can be
asserted exactly.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class RecordingTrigger(Trigger):
    """A core ``Trigger`` firing a fixed number of times and counting closes.

    Lets the ``TriggeredBatch`` driver's close handling be asserted directly:
    ``closes`` counts every ``close()`` call, and ``close_error`` makes the
    close itself fail so the driver's suppression can be exercised.

    ``first_ordinal`` stands in for a custom trigger whose ordinals are not a
    fresh 1-based per-stream counter: an offset numbers the fires from there,
    and ``None`` omits ``fire_ordinal`` entirely, since carrying it is a
    convention of this package's triggers rather than a ``Trigger`` guarantee.
    """

    def __init__(
        self,
        *,
        fires: int,
        close_error: BaseException | None = None,
        first_ordinal: int | None = 1,
    ) -> None:
        self._fires = fires
        self._close_error = close_error
        self._first_ordinal = first_ordinal
        self.closes = 0

    @property
    def name(self) -> str:
        return "RecordingTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        if self._first_ordinal is None:
            for _ in range(self._fires):
                yield RunRequest()
            return
        for offset in range(self._fires):
            yield RunRequest(parameters={"fire_ordinal": self._first_ordinal + offset})

    async def close(self) -> None:
        self.closes += 1
        if self._close_error is not None:
            raise self._close_error


class InFlightCounter:
    """Track live and peak concurrency across cooperating item tasks."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        self.current -= 1


class StubAgent:
    """A scripted per-item agent callable recording every invocation.

    Behaviour is keyed off the item value so a batch can mix succeeding,
    failing, slow, and flaky items deterministically.
    """

    def __init__(
        self,
        *,
        fail_items: set[object] | None = None,
        fail_times: dict[object, int] | None = None,
        latency: float = 0.0,
        counter: InFlightCounter | None = None,
        transform: Callable[[object], object] | None = None,
    ) -> None:
        self._fail_items = set(fail_items or set())
        self._fail_times = dict(fail_times or {})
        self._latency = latency
        self._counter = counter
        self._transform = transform
        self.calls: list[object] = []
        self.cancelled = 0

    async def __call__(self, item: object) -> object:
        self.calls.append(item)
        remaining = self._fail_times.get(item, 0)
        if remaining > 0:
            self._fail_times[item] = remaining - 1
            raise RuntimeError(f"transient failure for {item!r}")
        if item in self._fail_items:
            raise RuntimeError(f"permanent failure for {item!r}")
        counter = self._counter
        if counter is not None:
            counter.enter()
        try:
            if self._latency:
                await asyncio.sleep(self._latency)
            return self._transform(item) if self._transform is not None else f"done:{item}"
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        finally:
            if counter is not None:
                counter.leave()


class TrackingIterable:
    """An iterable that records how many items have been pulled (backpressure)."""

    def __init__(self, items: list[object]) -> None:
        self._items = items
        self.pulled = 0

    def __iter__(self) -> TrackingIterable:
        self._index = 0
        return self

    def __next__(self) -> object:
        if self._index >= len(self._items):
            raise StopIteration
        item = self._items[self._index]
        self._index += 1
        self.pulled += 1
        return item


def gated_agent(
    gate: asyncio.Event, counter: InFlightCounter
) -> Callable[[object], Awaitable[object]]:
    """Return an agent callable that blocks on ``gate`` while counting in-flight."""

    async def _run(item: object) -> object:
        counter.enter()
        try:
            await gate.wait()
            return f"done:{item}"
        finally:
            counter.leave()

    return _run
