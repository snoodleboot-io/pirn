"""Round-trip and validation tests for :class:`FastqFormat`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats.fastq_format import (
    FastqFormat,
)
from pirn.domains.connectors.file_formats.streaming_file_format import (
    StreamingFileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestFastqFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = FastqFormat()
        assert fmt.encoding == "utf-8"

    def test_custom_encoding(self) -> None:
        fmt = FastqFormat(encoding="ascii")
        assert fmt.encoding == "ascii"

    def test_encoding_must_be_str(self) -> None:
        with self.assertRaises(TypeError):
            FastqFormat(encoding=1)  # type: ignore[arg-type]

    def test_encoding_must_be_nonempty(self) -> None:
        with self.assertRaises(ValueError):
            FastqFormat(encoding="")


class TestFastqFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert FastqFormat().name == "fastq"

    def test_streaming_property(self) -> None:
        assert FastqFormat().streaming is True

    def test_inherits_streaming_base(self) -> None:
        assert isinstance(FastqFormat(), StreamingFileFormat)


class TestFastqFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        fmt = FastqFormat()
        records = [
            {
                "seq_id": "read1",
                "description": "lane=1",
                "sequence": "ACGTACGT",
                "quality": "IIIIIIII",
            },
            {
                "seq_id": "read2",
                "description": "lane=1",
                "sequence": "TGCATGCA",
                "quality": "JJJJJJJJ",
            },
            {
                "seq_id": "read3",
                "description": "lane=2",
                "sequence": "GATTACAG",
                "quality": "########",
            },
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty(self) -> None:
        fmt = FastqFormat()
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_single(self) -> None:
        fmt = FastqFormat()
        records = [
            {
                "seq_id": "solo",
                "description": "",
                "sequence": "ACGT",
                "quality": "IIII",
            }
        ]
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_quality_length_mismatch_rejected(self) -> None:
        fmt = FastqFormat()
        records = [
            {
                "seq_id": "bad",
                "description": "",
                "sequence": "ACGT",
                "quality": "II",
            }
        ]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)

    async def test_seq_id_with_whitespace_rejected(self) -> None:
        fmt = FastqFormat()
        records = [
            {
                "seq_id": "bad id",
                "description": "",
                "sequence": "ACGT",
                "quality": "IIII",
            }
        ]
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, records)
