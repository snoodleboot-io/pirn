"""Tests for :class:`ClinicalRecordPassThrough`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig

from pirn_health.clinical.clinical_record_pass_through import ClinicalRecordPassThrough
from pirn_health.types.clinical_record import ClinicalRecord


def _record(patient_id: str = "P1") -> ClinicalRecord:
    return ClinicalRecord(
        patient_id=patient_id,
        encounter_id="E1",
        observed_at=datetime.now(UTC),
    )


class TestPassThroughConstruction(unittest.TestCase):
    def test_construction(self) -> None:
        records = (_record(),)
        knot = ClinicalRecordPassThrough(
            records=records,
            _config=KnotConfig(id="pt"),
        )
        self.assertIsInstance(knot, ClinicalRecordPassThrough)


class TestPassThroughProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_records_unchanged(self) -> None:
        r1 = _record("P1")
        r2 = _record("P2")
        knot = ClinicalRecordPassThrough(
            records=(r1, r2),
            _config=KnotConfig(id="pt"),
        )
        result = await knot.process(records=(r1, r2), **{})
        self.assertEqual(result, (r1, r2))

    async def test_empty_records(self) -> None:
        knot = ClinicalRecordPassThrough(
            records=(),
            _config=KnotConfig(id="pt"),
        )
        result = await knot.process(records=(), **{})
        self.assertEqual(result, ())
