"""Round-trip and validation tests for :class:`FeatherFormat`."""

from __future__ import annotations

import unittest

try:
    import pyarrow
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e
try:
    import pyarrow.feather  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow.feather not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.feather_format import (
    FeatherFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestFeatherFormatConstruction(unittest.TestCase):
    def test_default_compression_is_none(self) -> None:
        fmt = FeatherFormat()
        assert fmt.compression is None

    def test_valid_compression(self) -> None:
        fmt = FeatherFormat(compression="zstd")
        assert fmt.compression == "zstd"

    def test_invalid_compression_value(self) -> None:
        with self.assertRaises(ValueError):
            FeatherFormat(compression="snappy")

    def test_invalid_compression_type(self) -> None:
        with self.assertRaises(TypeError):
            FeatherFormat(compression=42)  # type: ignore[arg-type]


class TestFeatherFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert FeatherFormat().name == "feather"

    def test_streaming_property(self) -> None:
        assert FeatherFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(FeatherFormat(), BatchFileFormat)


class TestFeatherFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
            {"id": 4, "name": "delta", "score": 4.0, "active": True},
        ]
        fmt = FeatherFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_with_zstd(self) -> None:
        records = [
            {"id": 10, "label": "x"},
            {"id": 11, "label": "y"},
        ]
        fmt = FeatherFormat(compression="zstd")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_uncompressed(self) -> None:
        records = [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]
        fmt = FeatherFormat(compression="uncompressed")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = FeatherFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        # PyArrow tolerates zero pylist rows: ``Table.from_pylist([])``
        # produces an empty table with no columns. Feather then
        # serialises an empty file; on read we get an empty list back.
        fmt = FeatherFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert decoded == []
