"""Round-trip and validation tests for :class:`CramFormat`.

CRAM is reference-based, so each round-trip needs an on-disk FASTA. The
``_reference_fixture`` helper builds a tiny single-contig FASTA in a
``tmp_path`` and indexes it with :func:`pysam.faidx` so htslib can use
it for reference-based decompression.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import pysam  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pysam not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.cram_format import (
    CramFormat,
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
            "pos": 1,
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
            "pos": 11,
            "mapq": 50,
            "cigar": "10M",
            "rnext": "*",
            "pnext": 0,
            "tlen": 0,
            "seq": "GTACGTACGT",
            "qual": "JJJJJJJJJJ",
        },
        {
            "qname": "read3",
            "flag": 0,
            "rname": "chr1",
            "pos": 21,
            "mapq": 40,
            "cigar": "10M",
            "rnext": "*",
            "pnext": 0,
            "tlen": 0,
            "seq": "ACGTACGTAC",
            "qual": "KKKKKKKKKK",
        },
    ]


def _reference_fixture(tmp_path: Path) -> str:
    """Write a tiny single-contig FASTA + .fai index, return path."""
    import pysam

    sequence = "ACGTACGTAC" * 20  # 200bp, enough for our reads
    fasta_path = tmp_path / "ref.fasta"
    fasta_path.write_text(f">chr1\n{sequence}\n")
    pysam.faidx(str(fasta_path))
    return str(fasta_path)


class TestCramFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = CramFormat()
        assert fmt.reference_fasta is None
        assert fmt.header_lines is None

    def test_explicit_reference(self) -> None:
        fmt = CramFormat(reference_fasta="/tmp/ref.fasta")
        assert fmt.reference_fasta == "/tmp/ref.fasta"

    def test_invalid_reference_type(self) -> None:
        with self.assertRaises(ValueError):
            CramFormat(reference_fasta="")

    def test_invalid_header_type(self) -> None:
        with self.assertRaises(TypeError):
            CramFormat(header_lines="not-a-sequence")  # type: ignore[arg-type]

    def test_empty_header_line_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CramFormat(header_lines=("@HD\tVN:1.6", ""))

    def test_header_line_without_at_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CramFormat(header_lines=("HD\tVN:1.6",))


class TestCramFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert CramFormat().name == "cram"

    def test_streaming_property(self) -> None:
        assert CramFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(CramFormat(), BatchFileFormat)


class TestCramFormatWriteValidation(unittest.IsolatedAsyncioTestCase):
    async def test_write_without_reference_raises(self) -> None:
        fmt = CramFormat()
        records = _alignment_records()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)


class TestCramFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        _td_test_round_trip_basic = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_round_trip_basic.cleanup)
        tmp_path = Path(_td_test_round_trip_basic.name)
        ref = _reference_fixture(tmp_path)
        records = _alignment_records()
        fmt = CramFormat(
            reference_fasta=ref,
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:200"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        _td_test_round_trip_empty = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_round_trip_empty.cleanup)
        tmp_path = Path(_td_test_round_trip_empty.name)
        ref = _reference_fixture(tmp_path)
        fmt = CramFormat(
            reference_fasta=ref,
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:200"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        _td_test_round_trip_single = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_round_trip_single.cleanup)
        tmp_path = Path(_td_test_round_trip_single.name)
        ref = _reference_fixture(tmp_path)
        records = [_alignment_records()[0]]
        fmt = CramFormat(
            reference_fasta=ref,
            header_lines=("@HD\tVN:1.6", "@SQ\tSN:chr1\tLN:200"),
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)
