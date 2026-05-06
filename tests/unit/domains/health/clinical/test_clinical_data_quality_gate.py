"""Unit tests for :class:`ClinicalDataQualityCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.clinical_data_quality_gate import (
    ClinicalDataQualityCheck,
    ClinicalDataQualityError,
    ClinicalDataQualityGate,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="g")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_records(self) -> None:
        knot = ClinicalDataQualityCheck(records=(), min_completeness=0.5, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42, min_completeness=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_record_in_sequence(self) -> None:
        knot = ClinicalDataQualityCheck(records=(), min_completeness=0.5, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(records=["not-a-record"], min_completeness=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = ClinicalDataQualityCheck(records=(), min_completeness=0.5, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "numeric"):
            await knot.process(records=(), min_completeness="x")  # type: ignore[arg-type]

    async def test_rejects_out_of_range_threshold(self) -> None:
        knot = ClinicalDataQualityCheck(records=(), min_completeness=0.5, _config=_CFG)
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(records=(), min_completeness=1.5)

    async def test_pass_through_when_completeness_above_threshold(self) -> None:
        records = (ClinicalRecord(observation_codes=("A",)),)
        knot = ClinicalDataQualityCheck(records=records, min_completeness=0.5, _config=_CFG)
        out = await knot.process(records=records, min_completeness=0.5)
        assert isinstance(out, tuple)
        assert len(out) == 1

    async def test_raises_when_completeness_below_threshold(self) -> None:
        records = (ClinicalRecord(observation_codes=()),)
        knot = ClinicalDataQualityCheck(records=records, min_completeness=0.5, _config=_CFG)
        with self.assertRaises(ClinicalDataQualityError):
            await knot.process(records=records, min_completeness=0.5)

    def test_alias_is_same_class(self) -> None:
        assert ClinicalDataQualityGate is ClinicalDataQualityCheck
