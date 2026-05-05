"""Unit tests for IterableSource."""

from __future__ import annotations

import unittest

from pirn.streaming.iterable import IterableSource


class TestIterableSourceConstruction(unittest.TestCase):
    def test_sync_iterable(self) -> None:
        src = IterableSource([1, 2, 3], parameter_name="x")
        self.assertEqual(src.parameter_name, "x")
        self.assertEqual(src.name, "IterableSource")

    def test_custom_name(self) -> None:
        src = IterableSource([], parameter_name="x", name="MySource")
        self.assertEqual(src.name, "MySource")


class TestIterableSourceStream(unittest.IsolatedAsyncioTestCase):
    async def test_yields_sync_items(self) -> None:
        src = IterableSource([10, 20, 30], parameter_name="val")
        collected = []
        async for v in src.stream():
            collected.append(v)
        self.assertEqual(collected, [10, 20, 30])

    async def test_yields_async_items(self) -> None:
        async def _agen():
            for i in range(3):
                yield i

        src = IterableSource(_agen(), parameter_name="v")
        collected = []
        async for v in src.stream():
            collected.append(v)
        self.assertEqual(collected, [0, 1, 2])

    async def test_empty_iterable(self) -> None:
        src = IterableSource([], parameter_name="x")
        collected = []
        async for v in src.stream():
            collected.append(v)
        self.assertEqual(collected, [])

    async def test_close_is_noop(self) -> None:
        src = IterableSource([1], parameter_name="x")
        await src.close()  # no exception
