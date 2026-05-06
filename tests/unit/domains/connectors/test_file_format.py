"""Tests for :class:`FileFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_format import FileFormat


async def _bytes_iter(*chunks: bytes):
    for chunk in chunks:
        yield chunk


async def _record_iter(*records):
    for r in records:
        yield r


class TestFileFormatInterface(unittest.IsolatedAsyncioTestCase):
    def test_streaming_default_is_false(self) -> None:
        fmt = FileFormat()
        self.assertFalse(fmt.streaming)

    async def test_name_raises_not_implemented(self) -> None:
        fmt = FileFormat()
        with self.assertRaises(NotImplementedError):
            _ = fmt.name

    async def test_read_raises_not_implemented(self) -> None:
        fmt = FileFormat()
        with self.assertRaises(NotImplementedError):
            await fmt.read(_bytes_iter())

    async def test_write_raises_not_implemented(self) -> None:
        fmt = FileFormat()
        with self.assertRaises(NotImplementedError):
            await fmt.write(_record_iter())


class TestFileFormatDrainHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_drain_bytes_joins_chunks(self) -> None:
        result = await FileFormat._drain_bytes(_bytes_iter(b"hello", b" ", b"world"))
        self.assertEqual(result, b"hello world")

    async def test_drain_bytes_empty(self) -> None:
        result = await FileFormat._drain_bytes(_bytes_iter())
        self.assertEqual(result, b"")

    async def test_drain_records_collects(self) -> None:
        recs = [{"a": 1}, {"b": 2}]
        result = await FileFormat._drain_records(_record_iter(*recs))
        self.assertEqual(result, recs)
