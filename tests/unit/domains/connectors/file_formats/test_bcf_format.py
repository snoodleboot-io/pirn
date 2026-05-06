"""Round-trip and validation tests for :class:`BcfFormat`."""

from __future__ import annotations

import unittest

try:
    import pysam  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pysam not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.bcf_format import (
    BcfFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestBcfFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = BcfFormat()
        assert fmt.header_lines is None

    def test_custom_header_lines(self) -> None:
        header_lines = (
            "##INFO=<ID=DP,Number=1,Type=Integer,Description=\"Depth\">",
            "##contig=<ID=chr1>",
        )
        fmt = BcfFormat(header_lines=header_lines)
        assert fmt.header_lines == header_lines

    def test_header_lines_must_be_sequence(self) -> None:
        with self.assertRaises(TypeError):
            BcfFormat(header_lines="##contig=<ID=chr1>")  # type: ignore[arg-type]

    def test_empty_header_line_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BcfFormat(header_lines=("##contig=<ID=chr1>", ""))


class TestBcfFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert BcfFormat().name == "bcf"

    def test_streaming_property(self) -> None:
        assert BcfFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(BcfFormat(), BatchFileFormat)


class TestBcfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {
                "chrom": "chr1",
                "pos": 100,
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 30.0,
                "filter": "PASS",
                "info": {"DP": "10"},
            },
            {
                "chrom": "chr1",
                "pos": 250,
                "id": "rs2",
                "ref": "G",
                "alt": "C",
                "qual": 50.0,
                "filter": "PASS",
                "info": {"DP": "15"},
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
        fmt = BcfFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty_with_header(self) -> None:
        header_lines = (
            "##INFO=<ID=DP,Number=1,Type=String,Description=\"Depth\">",
            "##contig=<ID=chr1>",
        )
        fmt = BcfFormat(header_lines=header_lines)
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_empty_without_header_fails(self) -> None:
        fmt = BcfFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_round_trip_single(self) -> None:
        records = [
            {
                "chrom": "chr1",
                "pos": 100,
                "id": "rs1",
                "ref": "A",
                "alt": "T",
                "qual": 30.0,
                "filter": "PASS",
                "info": {"DP": "10"},
            },
        ]
        fmt = BcfFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)
