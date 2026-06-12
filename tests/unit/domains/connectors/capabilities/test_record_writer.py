"""Tests for :class:`RecordWriter`."""

from __future__ import annotations

import unittest

from pirn.connectors.capabilities.record_writer import RecordWriter


class TestRecordWriterInterface(unittest.IsolatedAsyncioTestCase):
    async def test_write_records_raises_not_implemented(self) -> None:
        writer = RecordWriter()
        with self.assertRaises(NotImplementedError):
            await writer.write_records([{"id": 1}])
