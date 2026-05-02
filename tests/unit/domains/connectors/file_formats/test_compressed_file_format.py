"""Unit tests for :class:`CompressedFileFormat`.

Verifies that each supported codec composes correctly with a
streaming inner format (``JsonlFormat``), round-tripping records
through compress → decompress without loss.
"""

from __future__ import annotations

import pytest

from pirn.domains.connectors.file_formats.compressed_file_format import (
    CompressedFileFormat,
)
from pirn.domains.connectors.file_formats.jsonl_format import JsonlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestCompressedFileFormatConstruction:
    def test_inner_must_be_file_format(self) -> None:
        with pytest.raises(TypeError):
            CompressedFileFormat("not-a-format", codec="gzip")  # type: ignore[arg-type]

    def test_invalid_codec_raises(self) -> None:
        with pytest.raises(ValueError):
            CompressedFileFormat(JsonlFormat(), codec="brotli")

    def test_name_combines_inner_and_codec(self) -> None:
        fmt = CompressedFileFormat(JsonlFormat(), codec="gzip")
        assert fmt.name == "jsonl+gzip"

    def test_streaming_inherits_inner(self) -> None:
        fmt = CompressedFileFormat(JsonlFormat(), codec="gzip")
        assert fmt.streaming is True

    def test_inner_property(self) -> None:
        inner = JsonlFormat()
        fmt = CompressedFileFormat(inner, codec="zstd")
        assert fmt.inner is inner

    def test_codec_property(self) -> None:
        fmt = CompressedFileFormat(JsonlFormat(), codec="lz4")
        assert fmt.codec == "lz4"


class TestCompressedFileFormatGzip:
    @pytest.mark.asyncio
    async def test_round_trip_gzip(self) -> None:
        fmt = CompressedFileFormat(JsonlFormat(), codec="gzip")
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
            {"id": 3, "name": "gamma"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)


class TestCompressedFileFormatBzip2:
    @pytest.mark.asyncio
    async def test_round_trip_bzip2(self) -> None:
        fmt = CompressedFileFormat(JsonlFormat(), codec="bzip2")
        records = [
            {"id": 10, "tag": "x"},
            {"id": 20, "tag": "y"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)


class TestCompressedFileFormatZstd:
    @pytest.mark.asyncio
    async def test_round_trip_zstd(self) -> None:
        pytest.importorskip("zstandard")
        fmt = CompressedFileFormat(JsonlFormat(), codec="zstd")
        records = [
            {"id": 1, "value": 1.5},
            {"id": 2, "value": 2.5},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)


class TestCompressedFileFormatSnappy:
    @pytest.mark.asyncio
    async def test_round_trip_snappy(self) -> None:
        pytest.importorskip("snappy")
        fmt = CompressedFileFormat(JsonlFormat(), codec="snappy")
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
            {"id": 3, "name": "gamma"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)


class TestCompressedFileFormatLz4:
    @pytest.mark.asyncio
    async def test_round_trip_lz4(self) -> None:
        pytest.importorskip("lz4")
        fmt = CompressedFileFormat(JsonlFormat(), codec="lz4")
        records = [
            {"id": 1, "data": "alpha"},
            {"id": 2, "data": "beta"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
