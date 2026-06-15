"""Tests for :class:`FhirXmlFormat` — FHIR XML Bundle format."""

from __future__ import annotations

import sys
import unittest
import unittest.mock

try:
    import fhir  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("fhir not installed") from _e
try:
    import lxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lxml not installed") from _e
try:
    import defusedxml  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("defusedxml not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.fhir_xml_format import FhirXmlFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

_FHIR_NS = "http://hl7.org/fhir"


def _make_bundle_xml(resources_xml: list[str]) -> bytes:
    entries = "".join(
        f"<entry xmlns='{_FHIR_NS}'><resource>{r}</resource></entry>"
        for r in resources_xml
    )
    return (
        f"<?xml version='1.0' encoding='UTF-8'?>"
        f"<Bundle xmlns='{_FHIR_NS}'>"
        f"<type value='collection'/>"
        f"{entries}"
        f"</Bundle>"
    ).encode()


def _minimal_patient_xml() -> str:
    return (
        f"<Patient xmlns='{_FHIR_NS}'>"
        f"<id value='P001'/>"
        f"<name><family value='Doe'/></name>"
        f"<birthDate value='1990-01-01'/>"
        f"<address><city value='Boston'/></address>"
        f"<telecom><system value='phone'/></telecom>"
        f"<identifier value='P001'/>"
        f"<gender value='female'/>"
        f"</Patient>"
    )


async def _decode(fmt: FhirXmlFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestFhirXmlFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(FhirXmlFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert FhirXmlFormat().streaming is False

    def test_name(self) -> None:
        assert FhirXmlFormat().name == "fhir_xml"


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestFhirXmlFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    async def test_name_stripped(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert "name" not in data

    async def test_birth_date_stripped(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert "birthDate" not in data

    async def test_address_stripped(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert "address" not in data

    async def test_telecom_stripped(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert "telecom" not in data

    async def test_identifier_hashed(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert "identifier" not in data
        assert "identifier_hash" in data

    async def test_non_phi_field_preserved(self) -> None:
        payload = _make_bundle_xml([_minimal_patient_xml()])
        records = await _decode(FhirXmlFormat(), payload)
        data = records[0]["data"]
        assert data.get("gender") == "female"

    def test_phi_keywords_frozenset(self) -> None:
        assert isinstance(FhirXmlFormat._phi_keywords, frozenset)
        assert "name" in FhirXmlFormat._phi_keywords


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestFhirXmlFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_resource(self) -> None:
        records = [
            {
                "resource_type": "Observation",
                "resource_id": "obs-1",
                "status": "final",
                "data": {"resourceType": "Observation", "code": "8302-2"},
            }
        ]
        fmt = FhirXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["resource_type"] == "Observation"

    async def test_round_trip_two_resources(self) -> None:
        records = [
            {
                "resource_type": "Observation",
                "resource_id": "obs-1",
                "status": "final",
                "data": {"resourceType": "Observation"},
            },
            {
                "resource_type": "Condition",
                "resource_id": "cond-1",
                "status": "active",
                "data": {"resourceType": "Condition"},
            },
        ]
        fmt = FhirXmlFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestFhirXmlFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_xml_raises(self) -> None:
        fmt = FhirXmlFormat()

        async def _iter():
            yield b"not xml <<<<"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestFhirXmlFormatMissingDep(unittest.TestCase):
    def test_missing_fhir_raises(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"fhir": None, "fhir.resources": None}):
            fmt = FhirXmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_fhir()

    def test_missing_defusedxml_raises(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}
        ):
            fmt = FhirXmlFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_defusedxml()
