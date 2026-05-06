"""Unit tests for :class:`ClinicalTrialEligibilityFilter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.clinical_trial_eligibility_filter import (
    ClinicalTrialEligibilityFilter,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="f")
_RECORDS: tuple[ClinicalRecord, ...] = ()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_records(self) -> None:
        knot = ClinicalTrialEligibilityFilter(records=_RECORDS, criteria={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42, criteria={})  # type: ignore[arg-type]

    async def test_rejects_non_record(self) -> None:
        knot = ClinicalTrialEligibilityFilter(records=_RECORDS, criteria={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(records=["x"], criteria={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping_criteria(self) -> None:
        knot = ClinicalTrialEligibilityFilter(records=_RECORDS, criteria={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "criteria"):
            await knot.process(records=(), criteria=42)  # type: ignore[arg-type]

    async def test_rejects_non_callable_criterion(self) -> None:
        knot = ClinicalTrialEligibilityFilter(records=_RECORDS, criteria={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "callable"):
            await knot.process(records=(), criteria={"c1": "not-callable"})  # type: ignore[dict-item]

    async def test_filters_using_predicate(self) -> None:
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
        )
        knot = ClinicalTrialEligibilityFilter(records=records, criteria={}, _config=_CFG)
        out = await knot.process(
            records=records,
            criteria={"keep_a": lambda r: r.patient_id == "A"},
        )
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0].patient_id == "A"
