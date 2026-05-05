"""Unit tests for StreamingSource base and run_stream driver."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.streaming.base import StreamingSource, run_stream
from pirn.tapestry import Tapestry


class _Counting(Source):
    def __init__(self, *, received: list, **kwargs: Any) -> None:
        self._received = received
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> None:
        return None


class _SimpleStream(StreamingSource):
    def __init__(self, values: list) -> None:
        self._values = values
        self._closed = False

    @property
    def name(self) -> str:
        return "SimpleStream"

    @property
    def parameter_name(self) -> str:
        return "item"

    async def stream(self) -> AsyncIterator[Any]:
        for v in self._values:
            yield v

    async def close(self) -> None:
        self._closed = True


class TestStreamingSourceAbstract(unittest.TestCase):
    def test_name_raises_not_implemented(self) -> None:
        src = StreamingSource()
        with self.assertRaises(NotImplementedError):
            _ = src.name

    def test_parameter_name_raises_not_implemented(self) -> None:
        src = StreamingSource()
        with self.assertRaises(NotImplementedError):
            _ = src.parameter_name

    def test_stream_raises_not_implemented(self) -> None:
        src = StreamingSource()
        with self.assertRaises(NotImplementedError):
            src.stream()

    def test_close_raises_not_implemented(self) -> None:
        import asyncio
        src = StreamingSource()
        with self.assertRaises(NotImplementedError):
            asyncio.run(src.close())


class TestRunStream(unittest.IsolatedAsyncioTestCase):
    async def test_calls_on_result_for_each_value(self) -> None:
        results = []

        async def on_result(value: Any, result: Any) -> None:
            results.append(value)

        from pirn.nodes.source import Source as _Source

        class _Param(_Source):
            async def process(self_, **_: Any) -> None:
                return None

        received: list = []

        from pirn.core.parameter import Parameter

        with Tapestry() as t:
            Parameter("item", object, _config=KnotConfig(id="item"))

        stream = _SimpleStream([10, 20, 30])
        await run_stream(stream, t, on_result=on_result)
        self.assertEqual(results, [10, 20, 30])

    async def test_close_called_after_stream(self) -> None:
        with Tapestry() as t:
            from pirn.core.parameter import Parameter
            Parameter("item", object, _config=KnotConfig(id="item"))

        stream = _SimpleStream([1])
        await run_stream(stream, t)
        self.assertTrue(stream._closed)

    async def test_on_error_called_on_exception(self) -> None:
        errors: list = []

        async def on_err(value: Any, exc: BaseException) -> None:
            errors.append((value, exc))

        class _BrokenTapestry:
            async def run(self, request: Any) -> None:
                raise RuntimeError("boom")

        stream = _SimpleStream(["x"])
        await run_stream(stream, _BrokenTapestry(), on_error=on_err)  # type: ignore
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], "x")
