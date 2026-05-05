"""Unit tests for Trigger base class and run_forever driver."""

from __future__ import annotations

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

    @property
    def name(self) -> str:
        return "SimpleTrigger"

    async def stream(self) -> AsyncIterator[RunRequest]:
        for req in self._requests:
            yield req

    async def close(self) -> None:
        self._closed = True


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
