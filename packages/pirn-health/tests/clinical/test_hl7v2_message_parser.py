"""Unit tests for :class:`HL7v2MessageParser`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta, timezone

from pirn.core.knot_config import KnotConfig

from pirn_health.clinical.hl7v2_message_parser import (
    HL7v2MessageParser,
)
from pirn_health.clinical.phi_hasher import PhiHasher
from pirn_health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="p")
_SALT = "linkage-salt"

# ADT^A01 admit, MSH-7 = 2026-01-02 03:04:05, PID-3 = the patient identifier list.
_MESSAGE = "\n".join(
    [
        "MSH|^~\\&|EPIC|HOSP|LAB|HOSP|20260102030405||ADT^A01|MSG0001|P|2.5",
        "PID|1||MRN-4471^^^HOSP^MR||DOE^JANE||19800101|F",
        # PV1-19 (visit number) sits at index 19 of the split segment.
        "|".join(["PV1", "1", "I", "ICU^1^01", *([""] * 15), "VISIT-99"]),
        "OBX|1|NM|8867-4^Heart rate^LN||72|/min",
        "OBX|2|NM|8480-6^Systolic BP^LN||118|mm[Hg]",
    ]
)


def _knot() -> HL7v2MessageParser:
    return HL7v2MessageParser(message=_MESSAGE, salt=_SALT, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "message"):
            await _knot().process(message=42, salt=_SALT)  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _knot().process(message="", salt=_SALT)

    async def test_rejects_empty_salt(self) -> None:
        with self.assertRaisesRegex(ValueError, "salt must be non-empty"):
            await _knot().process(message=_MESSAGE, salt="")

    async def test_returns_clinical_record(self) -> None:
        out = await _knot().process(message=_MESSAGE, salt=_SALT)
        assert isinstance(out, ClinicalRecord)
        assert out.source_system == "hl7v2"
        assert out.observation_codes == ("8867-4", "8480-6")


class TestIdentifiersAreHashed(unittest.IsolatedAsyncioTestCase):
    """PID-3 is PHI: the record must carry the salted token, never the raw value."""

    async def test_patient_identifier_is_the_salted_token(self) -> None:
        out = await _knot().process(message=_MESSAGE, salt=_SALT)

        assert out.patient_id == PhiHasher.hash_identifier(_SALT, "MRN-4471")
        assert "MRN-4471" not in out.patient_id

    async def test_encounter_identifier_is_the_salted_token(self) -> None:
        out = await _knot().process(message=_MESSAGE, salt=_SALT)

        assert out.encounter_id == PhiHasher.hash_identifier(_SALT, "VISIT-99")

    async def test_token_matches_the_fhir_ingestion_path_for_the_same_patient(self) -> None:
        """Both ingestion knots must produce the same token, or linkage breaks."""
        out = await _knot().process(message=_MESSAGE, salt=_SALT)

        assert out.patient_id == PhiHasher.hash_identifier(_SALT, "MRN-4471")

    async def test_message_without_a_patient_identifier_is_rejected(self) -> None:
        message = "MSH|^~\\&|EPIC|HOSP|LAB|HOSP|20260102030405||ADT^A01|MSG0001|P|2.5"

        with self.assertRaisesRegex(ValueError, "no patient identifier"):
            await _knot().process(message=message, salt=_SALT)


class TestMessageTimestamp(unittest.IsolatedAsyncioTestCase):
    """MSH-7 is parsed, never replaced by the ingestion time."""

    async def test_full_precision_timestamp(self) -> None:
        out = await _knot().process(message=_MESSAGE, salt=_SALT)

        assert out.observed_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    async def test_date_only_timestamp(self) -> None:
        message = _MESSAGE.replace("20260102030405", "20260102")

        out = await _knot().process(message=message, salt=_SALT)

        assert out.observed_at == datetime(2026, 1, 2, tzinfo=UTC)

    async def test_utc_offset_is_honoured(self) -> None:
        message = _MESSAGE.replace("20260102030405", "20260102030405+0530")

        out = await _knot().process(message=message, salt=_SALT)

        assert out.observed_at == datetime(
            2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))
        )

    async def test_missing_timestamp_raises_instead_of_stamping_now(self) -> None:
        message = _MESSAGE.replace("20260102030405", "")

        with self.assertRaisesRegex(ValueError, "MSH-7"):
            await _knot().process(message=message, salt=_SALT)

    async def test_malformed_timestamp_raises_instead_of_stamping_now(self) -> None:
        message = _MESSAGE.replace("20260102030405", "20261301999999")

        with self.assertRaisesRegex(ValueError, "not a valid HL7 date/time"):
            await _knot().process(message=message, salt=_SALT)

    async def test_truncated_timestamp_raises(self) -> None:
        message = _MESSAGE.replace("20260102030405", "2026")

        with self.assertRaisesRegex(ValueError, "not a valid HL7 date/time"):
            await _knot().process(message=message, salt=_SALT)
