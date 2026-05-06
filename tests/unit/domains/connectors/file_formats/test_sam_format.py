"""Round-trip and validation tests for :class:`SamFormat`."""

from __future__ import annotations

import unittest

try:
    import pysam  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pysam not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.sam_format import (
    SamFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _alignment_records() -> list[dict[str, object]]:
    return [
        {
            "qname": "read1",
            "flag": 0,
            "rname": "chr1",
            "pos": 100,
            "mapq": 60,
            "cigar": "10M",
            "rnext": "*",
            "pnext": 0,
            "tlen": 0,
            "seq": "ACGTACGTAC",
            "qual": "IIIIIIIIII",
        },
        {
            "qname": "read2",
            "flag": 0,
            "rname": "chr1",
            "pos": 200,
            "mapq": 50,
            "cigar": "5M2I3M",
            "rnext": "*",
            "pnext": 0,
            "tlen": 0,
            "seq": "AAAAACCCCC",
            "qual": "JJJJJJJJJJ",
        },
        {
            "qname": "read3",
            "flag": 0,
            "rname": "chr1",
            "pos": 300,
            "mapq": 40,
            "cigar": "8M2S",
            "rnext": "*",
            "pnext": 0,
            "tlen": 0,
            "seq": "GGGGTTTTNN",
            "qual": "KKKKKKKKKK",
        },
    ]


class TestSamFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = SamFormat()
        assert fmt.header_lines is None

    def test_explicit_header_lines(self) -> None:
        header = ("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:248956422")
        fmt = SamFormat(header_lines=header)
        assert fmt.header_lines == header

    def test_invalid_header_type(self) -> None:
        with self.assertRaises(TypeError):
            SamFormat(header_lines="not-a-sequence")  # type: ignore[arg-type]

    def test_empty_header_line_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SamFormat(header_lines=("@HD\tVN:1.6", ""))

    def test_header_line_without_at_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SamFormat(header_lines=("HD\tVN:1.6",))


class TestSamFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert SamFormat().name == "sam"

    def test_streaming_property(self) -> None:
        assert SamFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(SamFormat(), BatchFileFormat)


class TestSamFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = _alignment_records()
        fmt = SamFormat(
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:1000000")
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_inferred_header(self) -> None:
        records = _alignment_records()
        fmt = SamFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = SamFormat(
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:1000")
        )
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        records = [_alignment_records()[0]]
        fmt = SamFormat(
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:1000")
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)
