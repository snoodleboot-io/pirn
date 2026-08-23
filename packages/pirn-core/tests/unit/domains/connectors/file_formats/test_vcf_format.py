"""Round-trip and validation tests for :class:`VcfFormat`."""

from __future__ import annotations

import unittest

from pirn.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)
from pirn.connectors.file_formats.vcf_format import (
    VcfFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestVcfFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = VcfFormat()
        assert fmt.encoding == "utf-8"
        assert fmt.fileformat == "VCFv4.3"

    def test_custom_arguments(self) -> None:
        fmt = VcfFormat(encoding="ascii", fileformat="VCFv4.2")
        assert fmt.encoding == "ascii"
        assert fmt.fileformat == "VCFv4.2"

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            VcfFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            VcfFormat(encoding="")

    def test_fileformat_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            VcfFormat(fileformat="")


class TestVcfFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert VcfFormat().name == "vcf"

    def test_streaming_property(self) -> None:
        assert VcfFormat().streaming is True

    def test_inherits_streaming_base(self) -> None:
        assert isinstance(VcfFormat(), StreamingFileFormat)


class TestVcfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = VcfFormat()
        records = [
            {
                "chrom": "chr1",
                "pos": 100,
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 30.0,
                "filter": "PASS",
                "info": {"DP": "10", "AF": "0.5"},
            },
            {
                "chrom": "chr1",
                "pos": 250,
                "id": ".",
                "ref": "G",
                "alt": "C",
                "qual": None,
                "filter": "PASS",
                "info": {},
            },
            {
                "chrom": "chr2",
                "pos": 1500,
                "id": "rs42",
                "ref": "C",
                "alt": "G",
                "qual": 99.5,
                "filter": "PASS",
                "info": {"DP": "20"},
            },
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = VcfFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        fmt = VcfFormat()
        records = [
            {
                "chrom": "chr1",
                "pos": 100,
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 50.0,
                "filter": "PASS",
                "info": {"DP": "12"},
            },
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_invalid_pos_rejected_on_write(self) -> None:
        fmt = VcfFormat()
        records = [
            {
                "chrom": "chr1",
                "pos": "100",
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 30.0,
                "filter": "PASS",
                "info": {},
            }
        ]
        with self.assertRaises(TypeError):
            await FormatRoundTrip.encode(fmt, records)

    async def test_missing_chrom_rejected(self) -> None:
        fmt = VcfFormat()
        records = [
            {
                "pos": 100,
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 30.0,
                "filter": "PASS",
                "info": {},
            }
        ]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)
