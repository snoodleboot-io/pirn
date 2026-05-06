"""Round-trip and validation tests for :class:`FastaFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.fasta_format import (
    FastaFormat,
)
from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestFastaFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = FastaFormat()
        assert fmt.encoding == "utf-8"
        assert fmt.line_width == 80

    def test_custom_arguments(self) -> None:
        fmt = FastaFormat(encoding="ascii", line_width=60)
        assert fmt.encoding == "ascii"
        assert fmt.line_width == 60

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            FastaFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            FastaFormat(encoding="")

    def test_line_width_must_be_int(self) -> None:
        with self.assertRaises(TypeError):
            FastaFormat(line_width="80")  # type: ignore[arg-type]

    def test_line_width_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            FastaFormat(line_width=0)


class TestFastaFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert FastaFormat().name == "fasta"

    def test_streaming_property(self) -> None:
        assert FastaFormat().streaming is True

    def test_inherits_streaming_base(self) -> None:
        assert isinstance(FastaFormat(), StreamingFileFormat)


class TestFastaFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = FastaFormat()
        records = [
            {
                "seq_id": "chr1",
                "description": "Homo sapiens chromosome 1",
                "sequence": "ACGT" * 25,
            },
            {
                "seq_id": "chr2",
                "description": "Homo sapiens chromosome 2",
                "sequence": "GATTACA",
            },
            {
                "seq_id": "chrM",
                "description": "mitochondrion",
                "sequence": "AAAA" * 30,
            },
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = FastaFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        fmt = FastaFormat()
        records = [
            {
                "seq_id": "seq42",
                "description": "synthetic",
                "sequence": "ACGTACGTACGT",
            }
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_no_description(self) -> None:
        fmt = FastaFormat()
        records = [
            {"seq_id": "bare", "description": "", "sequence": "ACGT"},
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_seq_id_with_whitespace_rejected(self) -> None:
        fmt = FastaFormat()
        records = [
            {"seq_id": "bad id", "description": "", "sequence": "ACGT"},
        ]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)

    async def test_missing_seq_id_rejected(self) -> None:
        fmt = FastaFormat()
        records = [{"description": "x", "sequence": "ACGT"}]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)
