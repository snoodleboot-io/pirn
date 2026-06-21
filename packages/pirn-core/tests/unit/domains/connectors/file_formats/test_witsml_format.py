"""Round-trip and validation tests for :class:`WitsmlFormat`."""

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
from pirn.connectors.file_formats.witsml_format import WitsmlFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _minimal_witsml_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<wellLogs xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
  <wellLog>
    <name>Log A</name>
    <wellName>Well-1</wellName>
  </wellLog>
  <wellLog>
    <name>Log B</name>
    <wellName>Well-2</wellName>
  </wellLog>
</wellLogs>
"""


def _simple_records() -> list[dict]:
    return [
        {"name": "Log A", "wellName": "Well-1"},
        {"name": "Log B", "wellName": "Well-2"},
    ]


class TestWitsmlFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert WitsmlFormat().name == "witsml"

    def test_streaming_false(self) -> None:
        assert WitsmlFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(WitsmlFormat(), BatchFileFormat)


class TestWitsmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_two_records(self) -> None:
        fmt = WitsmlFormat()
        records = _simple_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for orig, dec in zip(records, decoded, strict=False):
            for key, val in orig.items():
                assert dec.get(key) == val

    async def test_round_trip_single_record(self) -> None:
        fmt = WitsmlFormat()
        records = [{"name": "Test Log", "wellName": "Test-1"}]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0].get("name") == "Test Log"

    async def test_decode_minimal_witsml_xml(self) -> None:
        fmt = WitsmlFormat()

        async def _byte_iter():
            yield _minimal_witsml_xml()

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert len(records) == 2
        names = [r.get("name") for r in records]
        assert "Log A" in names
        assert "Log B" in names


class TestWitsmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_xml_raises(self) -> None:
        fmt = WitsmlFormat()

        async def _bad_iter():
            yield b"not xml at all <<<"

        with self.assertRaises(Exception):  # noqa: B017
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestWitsmlFormatMissingDep(unittest.TestCase):
    def test_defusedxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}
        ):
            fmt = WitsmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_defusedxml()

    def test_lxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
            fmt = WitsmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_lxml()
