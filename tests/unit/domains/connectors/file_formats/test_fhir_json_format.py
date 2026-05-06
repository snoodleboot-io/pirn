"""Tests for :class:`FhirJsonFormat` — FHIR JSON Bundle format."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
import unittest.mock

try:
    import fhir  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("fhir not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.fhir_json_format import FhirJsonFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bundle(resources: list[dict]) -> bytes:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }
    return json.dumps(bundle).encode("utf-8")


def _make_patient(patient_id: str = "P001") -> dict:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"family": "Doe", "given": ["Jane"]}],
        "birthDate": "1990-01-01",
        "address": [{"city": "Boston"}],
        "telecom": [{"system": "phone", "value": "555-0100"}],
        "identifier": [{"value": patient_id}],
        "gender": "female",
    }


async def _decode(fmt: FhirJsonFormat, payload: bytes) -> list[dict]:
    async def _iter():
        yield payload

    records = []
    async for rec in await fmt.read(_iter()):
        records.append(dict(rec))
    return records


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestFhirJsonFormatConstruction(unittest.TestCase):
    def test_is_batch_format(self) -> None:
        assert isinstance(FhirJsonFormat(), BatchFileFormat)

    def test_streaming_false(self) -> None:
        assert FhirJsonFormat().streaming is False

    def test_name(self) -> None:
        assert FhirJsonFormat().name == "fhir_json"


# ---------------------------------------------------------------------------
# PHI sanitisation
# ---------------------------------------------------------------------------

class TestFhirJsonFormatPhiSanitisation(unittest.IsolatedAsyncioTestCase):
    async def test_name_stripped(self) -> None:
        payload = _make_bundle([_make_patient()])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert "name" not in data

    async def test_birth_date_stripped(self) -> None:
        payload = _make_bundle([_make_patient()])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert "birthDate" not in data

    async def test_address_stripped(self) -> None:
        payload = _make_bundle([_make_patient()])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert "address" not in data

    async def test_telecom_stripped(self) -> None:
        payload = _make_bundle([_make_patient()])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert "telecom" not in data

    async def test_identifier_hashed(self) -> None:
        patient = _make_patient("P001")
        payload = _make_bundle([patient])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert "identifier" not in data
        assert "identifier_hash" in data
        expected = hashlib.sha256(
            json.dumps(patient["identifier"], sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        assert data["identifier_hash"] == expected

    async def test_non_phi_field_preserved(self) -> None:
        payload = _make_bundle([_make_patient()])
        records = await _decode(FhirJsonFormat(), payload)
        data = records[0]["data"]
        assert data.get("gender") == "female"

    async def test_phi_keywords_frozenset(self) -> None:
        assert isinstance(FhirJsonFormat._phi_keywords, frozenset)
        assert "name" in FhirJsonFormat._phi_keywords
        assert "birthDate" in FhirJsonFormat._phi_keywords


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestFhirJsonFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_single_resource(self) -> None:
        records = [
            {
                "resource_type": "Observation",
                "resource_id": "obs-1",
                "status": "final",
                "data": {"resourceType": "Observation", "code": "8302-2"},
            }
        ]
        fmt = FhirJsonFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 1
        assert decoded[0]["resource_type"] == "Observation"
        assert decoded[0]["resource_id"] == "obs-1"

    async def test_round_trip_multiple_resources(self) -> None:
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
        fmt = FhirJsonFormat()
        payload = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, payload)
        assert len(decoded) == 2
        resource_types = [d["resource_type"] for d in decoded]
        assert "Observation" in resource_types
        assert "Condition" in resource_types

    async def test_phi_stripped_after_round_trip(self) -> None:
        payload = _make_bundle([_make_patient()])
        fmt = FhirJsonFormat()
        decoded = await _decode(fmt, payload)
        assert "name" not in decoded[0]["data"]
        assert "birthDate" not in decoded[0]["data"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestFhirJsonFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_raises(self) -> None:
        fmt = FhirJsonFormat()

        async def _iter():
            yield b"not json at all {{{{"

        with self.assertRaises(Exception):  # noqa: B017
            async for _ in await fmt.read(_iter()):
                pass


# ---------------------------------------------------------------------------
# Missing dependency
# ---------------------------------------------------------------------------

class TestFhirJsonFormatMissingDep(unittest.TestCase):
    def test_missing_fhir_raises_import_error(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"fhir": None, "fhir.resources": None}):
            fmt = FhirJsonFormat()
            with self.assertRaisesRegex(ImportError, "pirn\\[health\\]"):
                fmt._load_fhir()
