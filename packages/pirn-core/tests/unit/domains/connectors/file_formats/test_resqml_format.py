"""Round-trip and validation tests for :class:`ResqmlFormat`."""

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
from pirn.connectors.file_formats.resqml_format import ResqmlFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _minimal_resqml_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<resqmlObjects xmlns="http://www.energistics.org/energyml/data/resqmlv2">
  <resqmlObject>
    <citation>
      <title>Grid A</title>
    </citation>
    <description>Top reservoir surface</description>
  </resqmlObject>
  <resqmlObject>
    <citation>
      <title>Grid B</title>
    </citation>
    <description>Base reservoir surface</description>
  </resqmlObject>
</resqmlObjects>
"""


def _simple_records() -> list[dict]:
    return [
        {"title": "Grid A", "description": "Top reservoir surface"},
        {"title": "Grid B", "description": "Base reservoir surface"},
    ]


def _simple_flat_records() -> list[dict]:
    """Records with no nested structure for clean round-trip."""
    return [
        {"description": "Top reservoir surface"},
        {"description": "Base reservoir surface"},
    ]


class TestResqmlFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert ResqmlFormat().name == "resqml"

    def test_streaming_false(self) -> None:
        assert ResqmlFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(ResqmlFormat(), BatchFileFormat)


class TestResqmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_two_records(self) -> None:
        fmt = ResqmlFormat()
        records = _simple_flat_records()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == len(records)
        for orig, dec in zip(records, decoded, strict=False):
            for key, val in orig.items():
                assert dec.get(key) == val

    async def test_round_trip_single_record(self) -> None:
        fmt = ResqmlFormat()
        records = [{"description": "Salt top"}]
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0].get("description") == "Salt top"

    async def test_decode_minimal_resqml_xml(self) -> None:
        fmt = ResqmlFormat()

        async def _byte_iter():
            yield _minimal_resqml_xml()

        record_iter = await fmt.read(_byte_iter())
        records = []
        async for r in record_iter:
            records.append(r)
        assert len(records) >= 1


class TestResqmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_xml_raises(self) -> None:
        fmt = ResqmlFormat()

        async def _bad_iter():
            yield b"<broken xml >>>"

        with self.assertRaises(Exception):  # noqa: B017
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestResqmlFormatMissingDep(unittest.TestCase):
    def test_defusedxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}
        ):
            fmt = ResqmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_defusedxml()

    def test_lxml_import_error_message(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
            fmt = ResqmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[oilgas\\]"):
                fmt._load_lxml()
