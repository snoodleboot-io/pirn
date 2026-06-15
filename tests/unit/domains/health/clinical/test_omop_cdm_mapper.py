"""Unit tests for :class:`OMOPCDMMapper`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_health.clinical.omop_cdm_mapper import OMOPCDMMapper
from pirn_health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="m")
_RECORD = ClinicalRecord(patient_id="P1", encounter_id="E1")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_record(self) -> None:
        knot = OMOPCDMMapper(record=_RECORD, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(record="x")  # type: ignore[arg-type]

    async def test_returns_tuple_of_rows(self) -> None:
        knot = OMOPCDMMapper(record=_RECORD, _config=_CFG)
        out = await knot.process(record=_RECORD)
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["person_id"] == "P1"
        assert out[0]["visit_occurrence_id"] == "E1"
