"""Unit tests for FileTailSource."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from pirn.streaming.file_tail import FileTailSource


class TestFileTailSourceConstruction(unittest.TestCase):
    def test_construction(self) -> None:
        src = FileTailSource("/tmp/test.log", parameter_name="line")
        self.assertEqual(src.parameter_name, "line")
        self.assertEqual(src.name, "FileTailSource")

    def test_custom_name(self) -> None:
        src = FileTailSource("/tmp/test.log", parameter_name="x", name="MyTail")
        self.assertEqual(src.name, "MyTail")

    def test_close_sets_closed_flag(self) -> None:
        src = FileTailSource("/tmp/test.log", parameter_name="line")
        self.assertFalse(src._closed)
        asyncio.run(src.close())
        self.assertTrue(src._closed)


class TestFileTailSourceStream(unittest.IsolatedAsyncioTestCase):
    async def test_reads_from_start(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            fname = f.name
        self.addCleanup(Path(fname).unlink, missing_ok=True)

        src = FileTailSource(fname, parameter_name="line", from_start=True)
        collected = []
        async for line in src.stream():
            collected.append(line)
            if len(collected) == 3:
                await src.close()
                break
        self.assertEqual(collected, ["line1", "line2", "line3"])

    async def test_close_stops_stream(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("alpha\n")
            fname = f.name
        self.addCleanup(Path(fname).unlink, missing_ok=True)

        src = FileTailSource(fname, parameter_name="line", from_start=True)
        count = 0
        async for _ in src.stream():
            count += 1
            await src.close()
        self.assertEqual(count, 1)
