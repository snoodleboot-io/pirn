"""Unit tests for :class:`ParquetFormat`."""

from __future__ import annotations
import unittest


try:
    import pyarrow
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

from pirn.domains.connectors.file_formats.parquet_format import ParquetFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestParquetFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = ParquetFormat()
        assert fmt.compression is None
        assert fmt.row_group_size == 50_000

    def test_explicit_compression(self) -> None:
        fmt = ParquetFormat(compression="zstd")
        assert fmt.compression == "zstd"

    def test_compression_must_be_str_or_none(self) -> None:
        with self.assertRaises(TypeError):
            ParquetFormat(compression=123)  # type: ignore[arg-type]

    def test_unsupported_compression_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ParquetFormat(compression="xyz")

    def test_row_group_size_must_be_int(self) -> None:
        with self.assertRaises(TypeError):
            ParquetFormat(row_group_size="50000")  # type: ignore[arg-type]

    def test_row_group_size_rejects_bool(self) -> None:
        with self.assertRaises(TypeError):
            ParquetFormat(row_group_size=True)  # type: ignore[arg-type]

    def test_row_group_size_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            ParquetFormat(row_group_size=0)
        with self.assertRaises(ValueError):
            ParquetFormat(row_group_size=-1)


class TestParquetFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert ParquetFormat().name == "parquet"

    def test_streaming_property(self) -> None:
        assert ParquetFormat().streaming is True


class TestParquetFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = ParquetFormat()
        records = [
            {"id": 1, "value": 1.5, "name": "alpha", "active": True, "note": None},
            {"id": 2, "value": 2.5, "name": "beta", "active": False, "note": "ok"},
            {"id": 3, "value": 3.5, "name": "gamma", "active": True, "note": None},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = ParquetFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = ParquetFormat()
        records = [{"id": 1, "value": 10.0, "name": "only", "active": True, "note": None}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_with_compression(self) -> None:
        fmt = ParquetFormat(compression="snappy", row_group_size=2)
        records = [
            {"k": i, "v": float(i) * 0.5, "label": f"row-{i}"}
            for i in range(5)
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
