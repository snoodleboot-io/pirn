"""Unit tests for :class:`ArrowIpcFormat`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

from pirn.connectors.file_formats.arrow_ipc_format import ArrowIpcFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestArrowIpcFormatConstruction(unittest.TestCase):
    def test_default_construction(self) -> None:
        fmt = ArrowIpcFormat()
        assert fmt.compression is None

    def test_explicit_compression(self) -> None:
        fmt = ArrowIpcFormat(compression="zstd")
        assert fmt.compression == "zstd"

    def test_compression_must_be_str_or_none(self) -> None:
        with self.assertRaises(TypeError):
            ArrowIpcFormat(compression=1)  # type: ignore[arg-type]

    def test_unsupported_compression_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ArrowIpcFormat(compression="snappy")
        with self.assertRaises(ValueError):
            ArrowIpcFormat(compression="xyz")


class TestArrowIpcFormatProperties(unittest.TestCase):
    def test_name(self) -> None:
        assert ArrowIpcFormat().name == "arrow_ipc"

    def test_streaming_property(self) -> None:
        assert ArrowIpcFormat().streaming is True


class TestArrowIpcFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = ArrowIpcFormat()
        records = [
            {"id": 1, "value": 1.5, "name": "alpha", "active": True, "note": None},
            {"id": 2, "value": 2.5, "name": "beta", "active": False, "note": "ok"},
            {"id": 3, "value": 3.5, "name": "gamma", "active": True, "note": None},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = ArrowIpcFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        fmt = ArrowIpcFormat()
        records = [{"id": 1, "value": 10.0, "name": "only", "active": True, "note": None}]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_with_compression(self) -> None:
        fmt = ArrowIpcFormat(compression="lz4")
        records = [
            {"k": i, "v": float(i) * 0.5, "label": f"row-{i}"}
            for i in range(5)
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)
