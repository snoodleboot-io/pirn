"""Unit tests for :class:`PatientCohortBuilder`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical.patient_cohort_builder import (
    PatientCohortBuilder,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord


_CFG = KnotConfig(id="b")
_RECORDS: tuple[ClinicalRecord, ...] = ()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_records(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42, stages={})  # type: ignore[arg-type]

    async def test_rejects_non_record(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(records=["x"], stages={})  # type: ignore[list-item]

    async def test_rejects_non_mapping_stages(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "stages"):
            await knot.process(records=(), stages=42)  # type: ignore[arg-type]

    async def test_rejects_non_mapping_stage_criteria(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "stage"):
            await knot.process(records=(), stages={"s1": 42})  # type: ignore[dict-item]

    async def test_runs_inner_pipeline(self) -> None:
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
        )
        knot = PatientCohortBuilder(
            records=records,
            stages={"keep_a": {"is_a": lambda r: r.patient_id == "A"}},
            _config=_CFG,
        )
        out = await knot.process(
            records=records,
            stages={"keep_a": {"is_a": lambda r: r.patient_id == "A"}},
        )
        assert isinstance(out, RunResult)
