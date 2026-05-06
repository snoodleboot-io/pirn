"""Unit tests for :class:`PHIRedactor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.phi_redactor import PHIRedactor
from pirn.domains.health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="r")
_RECORD = ClinicalRecord()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_record(self) -> None:
        knot = PHIRedactor(record=_RECORD, salt="s", _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(record="x", salt="s")  # type: ignore[arg-type]

    async def test_rejects_non_string_salt(self) -> None:
        knot = PHIRedactor(record=_RECORD, salt="s", _config=_CFG)
        with self.assertRaisesRegex(TypeError, "salt"):
            await knot.process(record=_RECORD, salt=42)  # type: ignore[arg-type]

    async def test_rejects_empty_salt(self) -> None:
        knot = PHIRedactor(record=_RECORD, salt="s", _config=_CFG)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(record=_RECORD, salt="")

    async def test_returns_redacted_record(self) -> None:
        record = ClinicalRecord(patient_id="P1", encounter_id="E1")
        knot = PHIRedactor(record=record, salt="seed", _config=_CFG)
        out = await knot.process(record=record, salt="seed")
        assert isinstance(out, ClinicalRecord)
        assert out.patient_id != "P1"
        assert out.encounter_id != "E1"
        assert len(out.patient_id) == 16
