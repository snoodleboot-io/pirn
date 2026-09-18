"""Unit tests for :class:`PatientCohortBuilder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_health.clinical.patient_cohort_builder import (
    PatientCohortBuilder,
)
from pirn_health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="b")
_RECORDS: tuple[ClinicalRecord, ...] = ()


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_records(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42, stages={})

    async def test_rejects_non_record(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await knot.process(records=["x"], stages={})

    async def test_rejects_non_mapping_stages(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "stages"):
            await knot.process(records=(), stages=42)

    async def test_rejects_non_mapping_stage_criteria(self) -> None:
        knot = PatientCohortBuilder(records=_RECORDS, stages={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "stage"):
            await knot.process(records=(), stages={"s1": 42})

    async def test_runs_inner_pipeline(self) -> None:
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
        )
        with Tapestry() as t:
            PatientCohortBuilder(
                records=records,
                stages={"keep_a": {"is_a": lambda r: r.patient_id == "A"}},
                _config=_CFG,
            )
        result = await t.run(RunRequest())
        assert result.succeeded

    async def test_chains_stages_through_the_graph(self) -> None:
        # Three records; stage 1 keeps A and B, stage 2 keeps only A. The two
        # ClinicalTrialEligibilityFilter knots must actually be chained
        # (records=previous), not each independently filtering the original
        # input, or stage 2 would never see stage 1's output.
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
            ClinicalRecord(patient_id="C"),
        )
        with Tapestry() as t:
            knot = PatientCohortBuilder(
                records=records,
                stages={
                    "drop_c": {"not_c": lambda r: r.patient_id != "C"},
                    "keep_a": {"is_a": lambda r: r.patient_id == "A"},
                },
                _config=_CFG,
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs[knot.knot_id]
        assert tuple(r.patient_id for r in output) == ("A",)
