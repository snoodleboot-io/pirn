"""Round-trip and validation tests for :class:`ProdmlFormat`."""

from __future__ import annotations

import sys
import unittest
import unittest.mock

try:
    import defusedxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("defusedxml not installed") from _e
try:
    import lxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lxml not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.prodml_format import ProdmlFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _minimal_prodml_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<prodmlObjects xmlns="http://www.prodml.org/schemas/1series">
  <prodmlObject>
    <facilityName>Platform A</facilityName>
    <oilRate>1234.5</oilRate>
  </prodmlObject>
  <prodmlObject>
    <facilityName>Platform B</facilityName>
    <oilRate>987.6</oilRate>
  </prodmlObject>
</prodmlObjects>
"""


def _simple_records() -> list[dict]:
    return [
        {"facilityName": "Platform A", "oilRate": "1234.5"},
        {"facilityName": "Platform B", "oilRate": "987.6"},
    ]


class TestProdmlFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert ProdmlFormat().name == "prodml"

    def test_streaming_false(self) -> None:
        assert ProdmlFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(ProdmlFormat(), BatchFileFormat)


class TestProdmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_two_records(self) -> None:
        fmt = ProdmlFormat()
        records = _simple_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for orig, dec in zip(records, decoded, strict=False):
            for key, val in orig.items():
                assert dec.get(key) == val

    async def test_round_trip_single_record(self) -> None:
        fmt = ProdmlFormat()
        records = [{"facilityName": "Test Platform", "gasRate": "500.0"}]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0].get("facilityName") == "Test Platform"

    async def test_decode_minimal_prodml_xml(self) -> None:
        fmt = ProdmlFormat()

        async def _byte_iter():
            yield _minimal_prodml_xml()

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert len(records) == 2


class TestProdmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_xml_raises(self) -> None:
        fmt = ProdmlFormat()

        async def _bad_iter():
            yield b"<unclosed"

        with self.assertRaises(Exception):  # noqa: B017
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestProdmlFormatMissingDep(unittest.TestCase):
    def test_defusedxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}
        ):
            fmt = ProdmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_defusedxml()

    def test_lxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
            fmt = ProdmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_lxml()
