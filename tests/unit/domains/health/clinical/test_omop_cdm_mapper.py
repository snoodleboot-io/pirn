"""Unit tests for :class:`OMOPCDMMapper`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.omop_cdm_mapper import OMOPCDMMapper
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_record(self) -> None:
        with pytest.raises(TypeError, match="ClinicalRecord"):
            OMOPCDMMapper(
                record="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="m"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_tuple_of_rows(self) -> None:
        with Tapestry() as t:
            OMOPCDMMapper(
                record=ClinicalRecord(patient_id="P1", encounter_id="E1"),
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0]["person_id"] == "P1"
        assert out[0]["visit_occurrence_id"] == "E1"
