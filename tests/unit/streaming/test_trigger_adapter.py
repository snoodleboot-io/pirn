"""Unit tests for StreamingSourceTrigger."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.streaming.base import StreamingSource
from pirn.streaming.trigger_adapter import StreamingSourceTrigger


class _FakeStream(StreamingSource):
    def __init__(self, values: list) -> None:
        self._values = values
        self._closed = False

    @property
    def name(self) -> str:
        return "FakeStream"

    @property
    def parameter_name(self) -> str:
        return "item"

    async def stream(self) -> AsyncIterator[Any]:
        for v in self._values:
            yield v

    async def close(self) -> None:
        self._closed = True


class TestStreamingSourceTriggerConstruction(unittest.TestCase):
    def test_name_includes_source_name(self) -> None:
        src = _FakeStream([])
        trigger = StreamingSourceTrigger(source=src)
        self.assertIn("FakeStream", trigger.name)


class TestStreamingSourceTriggerStream(unittest.IsolatedAsyncioTestCase):
    async def test_yields_run_requests(self) -> None:
        src = _FakeStream([1, 2, 3])
        trigger = StreamingSourceTrigger(source=src)
        requests = []
        async for req in trigger.stream():
            requests.append(req)
        self.assertEqual(len(requests), 3)
        self.assertIsInstance(requests[0], RunRequest)

    async def test_run_request_binds_parameter(self) -> None:
        src = _FakeStream(["hello"])
        trigger = StreamingSourceTrigger(source=src)
        async for req in trigger.stream():
            self.assertEqual(req.parameters["item"], "hello")

    async def test_custom_request_builder(self) -> None:
        def builder(value: Any) -> RunRequest:
            return RunRequest(parameters={"custom": value * 2})

        src = _FakeStream([5])
        trigger = StreamingSourceTrigger(source=src, request_builder=builder)
        async for req in trigger.stream():
            self.assertEqual(req.parameters["custom"], 10)

    async def test_close_delegates_to_source(self) -> None:
        src = _FakeStream([])
        trigger = StreamingSourceTrigger(source=src)
        await trigger.close()
        self.assertTrue(src._closed)
