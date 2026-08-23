"""Unit tests for Trigger base class and run_forever driver."""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger, run_forever


class _SimpleTrigger(Trigger):
    def __init__(self, requests: list[RunRequest]) -> None:
        self._requests = requests
        self._closed = False
        self.closes = 0

    @property
    def name(self) -> str:
        return "SimpleTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        for req in self._requests:
            yield req

    async def close(self) -> None:
        self._closed = True
        self.closes += 1


class _RepeatingTrigger(Trigger):
    """Fires once per loop turn, up to ``max_fires``.

    Bounded on purpose: a driver that ignores cancellation drains the stream
    and returns, so the test fails on its assertions instead of wedging.
    """

    def __init__(self, max_fires: int) -> None:
        self._max_fires = max_fires
        self.fires = 0
        self.closes = 0

    @property
    def name(self) -> str:
        return "RepeatingTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        while self.fires < self._max_fires:
            self.fires += 1
            yield RunRequest()
            await asyncio.sleep(0)

    async def close(self) -> None:
        self.closes += 1


class _SleepingTapestry:
    """Stands in for a Tapestry whose run awaits, so it is genuinely cancellable.

    ``delay`` is writable so the test can release the loop after it has
    cancelled: a driver that swallowed the cancellation then finishes quickly
    rather than parking again on the next fire.
    """

    def __init__(self) -> None:
        self.delay = 3600.0

    async def run(self, request: RunRequest) -> object:
        await asyncio.sleep(self.delay)
        return object()


class TestTriggerAbstract(unittest.TestCase):
    def test_name_raises(self) -> None:
        t = Trigger()
        with self.assertRaises(NotImplementedError):
            _ = t.name

    def test_stream_raises(self) -> None:
        t = Trigger()
        with self.assertRaises(NotImplementedError):
            t.stream()

    def test_close_raises(self) -> None:
        import asyncio

        t = Trigger()
        with self.assertRaises(NotImplementedError):
            asyncio.run(t.close())


class TestRunForever(unittest.IsolatedAsyncioTestCase):
    async def test_runs_each_request(self) -> None:
        results = []

        async def on_result(req: RunRequest, result: Any) -> None:
            results.append(req)

        tapestry = MagicMock()
        tapestry.run = AsyncMock(return_value=MagicMock())

        reqs = [RunRequest(), RunRequest()]
        trigger = _SimpleTrigger(reqs)
        await run_forever(trigger, tapestry, on_result=on_result)
        self.assertEqual(len(results), 2)

    async def test_close_called_after_stream(self) -> None:
        tapestry = MagicMock()
        tapestry.run = AsyncMock(return_value=MagicMock())
        trigger = _SimpleTrigger([])
        await run_forever(trigger, tapestry)
        self.assertTrue(trigger._closed)

    async def test_on_error_called_on_exception(self) -> None:
        errors = []

        async def on_error(req: RunRequest, exc: BaseException) -> None:
            errors.append(exc)

        tapestry = MagicMock()
        tapestry.run = AsyncMock(side_effect=RuntimeError("boom"))

        trigger = _SimpleTrigger([RunRequest()])
        await run_forever(trigger, tapestry, on_error=on_error)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)


class TestRunForeverNeverSwallowsShutdown(unittest.IsolatedAsyncioTestCase):
    """``on_error`` observes failures, never the signals that end the process.

    Mirrors ``TriggeredBatch``'s ``test_on_error_never_swallows_cancellation``
    in pirn-agents so the two drivers cannot drift: the exception propagates,
    ``on_error`` is not consulted, and the trigger is still closed.
    """

    async def test_on_error_never_swallows_cancellation(self) -> None:
        observed: list[BaseException] = []

        async def on_error(request: RunRequest, exc: BaseException) -> None:
            observed.append(exc)

        tapestry = MagicMock()
        tapestry.run = AsyncMock(side_effect=asyncio.CancelledError)

        trigger = _SimpleTrigger([RunRequest()])
        with self.assertRaises(asyncio.CancelledError):
            await run_forever(trigger, tapestry, on_error=on_error)
        self.assertEqual(observed, [])
        self.assertEqual(trigger.closes, 1)

    async def test_on_error_never_swallows_keyboard_interrupt(self) -> None:
        observed: list[BaseException] = []

        async def on_error(request: RunRequest, exc: BaseException) -> None:
            observed.append(exc)

        tapestry = MagicMock()
        tapestry.run = AsyncMock(side_effect=KeyboardInterrupt)

        trigger = _SimpleTrigger([RunRequest()])
        with self.assertRaises(KeyboardInterrupt):
            await run_forever(trigger, tapestry, on_error=on_error)
        self.assertEqual(observed, [])
        self.assertEqual(trigger.closes, 1)

    async def test_on_error_never_swallows_system_exit(self) -> None:
        observed: list[BaseException] = []

        async def on_error(request: RunRequest, exc: BaseException) -> None:
            observed.append(exc)

        tapestry = MagicMock()
        tapestry.run = AsyncMock(side_effect=SystemExit)

        trigger = _SimpleTrigger([RunRequest()])
        with self.assertRaises(SystemExit):
            await run_forever(trigger, tapestry, on_error=on_error)
        self.assertEqual(observed, [])
        self.assertEqual(trigger.closes, 1)

    async def test_cancelling_the_driving_task_actually_stops_the_loop(self) -> None:
        """A real ``task.cancel()`` must end the run, not be logged and ignored.

        ``asyncio.wait`` bounds this so a regression fails in a second rather
        than wedging the suite: before the fix the observer absorbed the
        ``CancelledError``, the loop kept firing, and ``await task`` never
        returned.
        """
        observed: list[BaseException] = []

        async def on_error(request: RunRequest, exc: BaseException) -> None:
            observed.append(exc)

        trigger = _RepeatingTrigger(max_fires=5)
        tapestry = _SleepingTapestry()
        task = asyncio.create_task(run_forever(trigger, tapestry, on_error=on_error))

        await asyncio.sleep(0.05)
        fires_at_cancel = trigger.fires
        task.cancel()
        tapestry.delay = 0.0
        _done, pending = await asyncio.wait([task], timeout=1.0)

        self.assertEqual(pending, set(), "run_forever kept running after cancel()")
        self.assertTrue(task.cancelled())
        self.assertEqual(observed, [])
        self.assertEqual(trigger.fires, fires_at_cancel)
        self.assertEqual(trigger.closes, 1)
