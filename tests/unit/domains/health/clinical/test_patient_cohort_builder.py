"""Unit tests for :class:`PatientCohortBuilder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical.patient_cohort_builder import (
    PatientCohortBuilder,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            PatientCohortBuilder(
                records=42,  # type: ignore[arg-type]
                stages={},
                _config=KnotConfig(id="b"),
            )

    def test_rejects_non_record(self) -> None:
        with pytest.raises(TypeError, match="ClinicalRecord"):
            PatientCohortBuilder(
                records=["x"],  # type: ignore[list-item]
                stages={},
                _config=KnotConfig(id="b"),
            )

    def test_rejects_non_mapping_stages(self) -> None:
        with pytest.raises(TypeError, match="stages"):
            PatientCohortBuilder(
                records=(),
                stages=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="b"),
            )

    def test_rejects_non_mapping_stage_criteria(self) -> None:
        with pytest.raises(TypeError, match="stage"):
            PatientCohortBuilder(
                records=(),
                stages={"s1": 42},  # type: ignore[dict-item]
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_runs_inner_pipeline(self) -> None:
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
        )
        with Tapestry() as t:
            PatientCohortBuilder(
                records=records,
                stages={"keep_a": {"is_a": lambda r: r.patient_id == "A"}},
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, RunResult)
