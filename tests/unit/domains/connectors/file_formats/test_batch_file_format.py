"""Tests for :class:`BatchFileFormat`."""

from __future__ import annotations

import unittest
from typing import Any, AsyncIterator, Iterable, Mapping

from pirn.domains.connectors.file_formats.batch_file_format import BatchFileFormat


async def _bytes_iter(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def _record_iter(*records) -> AsyncIterator[Mapping[str, Any]]:
    for r in records:
        yield r


class _SimpleBatchFormat(BatchFileFormat):
    @property
    def name(self) -> str:
        return "simple"

    async def _decode_full(self, payload: bytes) -> Iterable[Mapping[str, Any]]:
        import json
        return json.loads(payload.decode())

    async def _encode_full(self, records: Iterable[Mapping[str, Any]]) -> bytes:
        import json
        return json.dumps(list(records)).encode()


class TestBatchFileFormatStreaming(unittest.TestCase):
    def test_streaming_is_false(self) -> None:
        fmt = _SimpleBatchFormat()
        self.assertFalse(fmt.streaming)


class TestBatchFileFormatInterface(unittest.IsolatedAsyncioTestCase):
    async def test_decode_full_raises_not_implemented_on_base(self) -> None:
        fmt = BatchFileFormat()
        with self.assertRaises(NotImplementedError):
            await fmt._decode_full(b"")

    async def test_encode_full_raises_not_implemented_on_base(self) -> None:
        fmt = BatchFileFormat()
        with self.assertRaises(NotImplementedError):
            await fmt._encode_full([])

    async def test_read_decodes_records(self) -> None:
        import json
        fmt = _SimpleBatchFormat()
        payload = json.dumps([{"a": 1}, {"b": 2}]).encode()
        stream = _bytes_iter(payload)
        result_iter = await fmt.read(stream)
        records = [r async for r in result_iter]
        self.assertEqual(records, [{"a": 1}, {"b": 2}])

    async def test_write_encodes_records(self) -> None:
        fmt = _SimpleBatchFormat()
        records = _record_iter({"x": 10})
        byte_iter = await fmt.write(records)
        chunks = [c async for c in byte_iter]
        import json
        decoded = json.loads(b"".join(chunks).decode())
        self.assertEqual(decoded, [{"x": 10}])
