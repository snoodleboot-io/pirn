"""Tests for :class:`SegdFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.segd_format import SegdFormat


def _synthetic_gh1(
    record_length_bcd: int = 0x6000,  # 6000 ms BCD
    channel_count_bcd: int = 0x0096,  # 96 channels BCD
    sample_interval_bcd: int = 0x0002,  # 2 * (1/16) ms
) -> bytes:
    """Build a synthetic 32-byte SEG-D General Header Block 1."""
    header = bytearray(32)
    # Bytes 14-15: record length BCD
    header[14] = (record_length_bcd >> 8) & 0xFF
    header[15] = record_length_bcd & 0xFF
    # Bytes 16-17: channel count BCD
    header[16] = (channel_count_bcd >> 8) & 0xFF
    header[17] = channel_count_bcd & 0xFF
    # Bytes 18-19: sample interval BCD (1/16 ms units)
    header[18] = (sample_interval_bcd >> 8) & 0xFF
    header[19] = sample_interval_bcd & 0xFF
    return bytes(header)


class TestSegdFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert SegdFormat().name == "segd"

    def test_streaming_false(self) -> None:
        assert SegdFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(SegdFormat(), BatchFileFormat)


class TestSegdFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_synthetic_header(self) -> None:
        fmt = SegdFormat()
        payload = _synthetic_gh1(
            record_length_bcd=0x6000,
            channel_count_bcd=0x0096,
            sample_interval_bcd=0x0002,
        )

        async def _byte_iter():
            yield payload

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert len(records) == 1
        assert records[0]["raw_header"] == payload

    async def test_decode_returns_raw_header(self) -> None:
        fmt = SegdFormat()
        payload = _synthetic_gh1()

        async def _byte_iter():
            yield payload

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert "raw_header" in records[0]
        assert isinstance(records[0]["raw_header"], bytes)
        assert len(records[0]["raw_header"]) == 32

    async def test_decode_record_has_required_keys(self) -> None:
        fmt = SegdFormat()
        payload = _synthetic_gh1()

        async def _byte_iter():
            yield payload

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        r = records[0]
        assert "record_length" in r
        assert "channel_count" in r
        assert "sample_interval" in r
        assert "raw_header" in r


class TestSegdFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_encode_raises_not_implemented(self) -> None:
        fmt = SegdFormat()
        with self.assertRaisesRegex(NotImplementedError, "write is not supported"):
            await fmt._encode_full([])

    async def test_decode_too_short_raises(self) -> None:
        fmt = SegdFormat()
        with self.assertRaisesRegex(ValueError, "too short"):
            await fmt._decode_full(b"\x00" * 10)

    async def test_decode_non_bytes_raises(self) -> None:
        fmt = SegdFormat()
        with self.assertRaises(TypeError):
            await fmt._decode_full("not bytes")  # type: ignore[arg-type]
