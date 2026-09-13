"""Unit tests for :class:`FhirPatientAssembler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig

from pirn_health.assemblers.fhir_patient_assembler import FhirPatientAssembler
from pirn_health.clinical.phi_hasher import _PhiHasher
from pirn_health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="f")
_RECORDS = [{"patient_id": "P1", "encounter_id": "E1", "observation_codes": ["A"]}]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FhirPatientAssembler:
        return FhirPatientAssembler(records=_RECORDS, salt="seed", _config=_CFG)

    async def test_rejects_non_list_records(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records="x", salt="seed")  # type: ignore[arg-type]

    async def test_rejects_empty_records(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(records=[], salt="seed")

    async def test_rejects_non_string_salt(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "salt"):
            await knot.process(records=_RECORDS, salt=42)  # type: ignore[arg-type]

    async def test_rejects_empty_salt(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "salt"):
            await knot.process(records=_RECORDS, salt="")

    async def test_hashes_patient_and_encounter_id(self) -> None:
        knot = self._make_knot()
        out = await knot.process(records=_RECORDS, salt="seed")
        assert isinstance(out, tuple)
        assert len(out) == 1
        record = out[0]
        assert isinstance(record, ClinicalRecord)
        assert record.patient_id != "P1"
        assert record.encounter_id != "E1"
        assert record.patient_id == _PhiHasher.hash_identifier("seed", "P1")
        assert record.encounter_id == _PhiHasher.hash_identifier("seed", "E1")
        assert record.observation_codes == ("A",)

    async def test_different_salts_produce_different_hashes(self) -> None:
        knot = self._make_knot()
        out_a = await knot.process(records=_RECORDS, salt="salt-a")
        out_b = await knot.process(records=_RECORDS, salt="salt-b")
        assert out_a[0].patient_id != out_b[0].patient_id
