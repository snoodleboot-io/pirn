"""Tests for :class:`CdaXmlFormat` — CDA XML clinical document format."""

from __future__ import annotations

import sys
import unittest
import unittest.mock

try:
    import lxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lxml not installed") from _e
try:
    import defusedxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("defusedxml not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.cda_xml_format import CdaXmlFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

_CDA_NS = "urn:hl7-org:v3"


def _make_cda_xml(
    doc_id: str = "DOC001",
    template_id: str = "2.16.840.1.113883.3.27.1776",
    title: str = "Discharge Summary",
    effective_time: str = "20230601",
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="{_CDA_NS}">
  <id extension="{doc_id}"/>
  <templateId root="{template_id}"/>
  <title>{title}</title>
  <effectiveTime value="{effective_time}"/>
  <recordTarget>
    <patientRole>
      <patient>
        <name><given>Jane</given><family>Doe</family></name>
        <birthTime value="19900101"/>
        <addr><streetAddressLine>123 Main St</streetAddressLine></addr>
        <telecom value="tel:555-0100"/>
      </patient>
    </patientRole>
  </recordTarget>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11329-0"/>
          <text>History of present illness</text>
        </section>
      </component>
      <component>
        <section>
          <code code="10183-2"/>
          <text>Discharge medications</text>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
""".encode()


async def _decode(fmt: CdaXmlFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestCdaXmlFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(CdaXmlFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert CdaXmlFormat().streaming is False

    def test_name(self) -> None:
        assert CdaXmlFormat().name == "cda_xml"


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestCdaXmlFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    def test_phi_keywords_frozenset(self) -> None:
        assert isinstance(CdaXmlFormat._phi_keywords, frozenset)
        assert "name" in CdaXmlFormat._phi_keywords
        assert "birthTime" in CdaXmlFormat._phi_keywords
        assert "addr" in CdaXmlFormat._phi_keywords
        assert "telecom" in CdaXmlFormat._phi_keywords

    async def test_record_has_document_id(self) -> None:
        records = await _decode(CdaXmlFormat(), _make_cda_xml(doc_id="DOC001"))
        assert records[0]["document_id"] == "DOC001"

    async def test_record_has_title(self) -> None:
        records = await _decode(
            CdaXmlFormat(), _make_cda_xml(title="Discharge Summary")
        )
        assert records[0]["title"] == "Discharge Summary"

    async def test_record_has_effective_time(self) -> None:
        records = await _decode(
            CdaXmlFormat(), _make_cda_xml(effective_time="20230601")
        )
        assert records[0]["effective_time"] == "20230601"

    async def test_body_contains_sections(self) -> None:
        records = await _decode(CdaXmlFormat(), _make_cda_xml())
        body = records[0]["body"]
        assert "11329-0" in body
        assert "10183-2" in body


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestCdaXmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_document(self) -> None:
        records = [
            {
                "document_id": "DOC001",
                "template_id": "2.16.840.1.113883.3.27.1776",
                "title": "Discharge Summary",
                "effective_time": "20230601",
                "body": {"11329-0": "History text", "10183-2": "Medications"},
            }
        ]
        fmt = CdaXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["document_id"] == "DOC001"
        assert decoded[0]["title"] == "Discharge Summary"
        assert decoded[0]["effective_time"] == "20230601"

    async def test_round_trip_body_sections_preserved(self) -> None:
        records = [
            {
                "document_id": "DOC002",
                "template_id": "2.16.840.1.113883",
                "title": "Clinical Note",
                "effective_time": "20230701",
                "body": {"SECT-001": "Section text here"},
            }
        ]
        fmt = CdaXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert "SECT-001" in decoded[0]["body"]
        assert decoded[0]["body"]["SECT-001"] == "Section text here"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestCdaXmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_xml_raises(self) -> None:
        fmt = CdaXmlFormat()

        async def _iter():
            yield b"not xml <<<<"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass

    async def test_encode_empty_raises(self) -> None:
        fmt = CdaXmlFormat()

        async def _empty():
            return
            yield

        with self.assertRaisesRegex(ValueError, "empty"):
            async for _ in await fmt.write(_empty()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestCdaXmlFormatMissingDep(unittest.TestCase):
    def test_missing_defusedxml_raises(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}
        ):
            fmt = CdaXmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_defusedxml()

    def test_missing_lxml_raises(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
            fmt = CdaXmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_lxml()
