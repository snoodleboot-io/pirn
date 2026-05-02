"""Unit tests for :class:`ClinicalDataQualityGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.clinical_data_quality_gate import (
    ClinicalDataQualityError,
    ClinicalDataQualityGate,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            ClinicalDataQualityGate(
                records=42,  # type: ignore[arg-type]
                min_completeness=0.5,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_record_in_sequence(self) -> None:
        with pytest.raises(TypeError, match="ClinicalRecord"):
            ClinicalDataQualityGate(
                records=["not-a-record"],  # type: ignore[list-item]
                min_completeness=0.5,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            ClinicalDataQualityGate(
                records=(),
                min_completeness="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="g"),
            )

    def test_rejects_out_of_range_threshold(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            ClinicalDataQualityGate(
                records=(),
                min_completeness=1.5,
                _config=KnotConfig(id="g"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_pass_through_when_completeness_above_threshold(self) -> None:
        records = (ClinicalRecord(observation_codes=("A",)),)
        with Tapestry() as t:
            ClinicalDataQualityGate(
                records=records,
                min_completeness=0.5,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert isinstance(out, tuple)
        assert len(out) == 1

    async def test_raises_when_completeness_below_threshold(self) -> None:
        records = (ClinicalRecord(observation_codes=()),)
        with Tapestry() as t:
            ClinicalDataQualityGate(
                records=records,
                min_completeness=0.5,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        # Knot framework wraps the exception as Err
        assert any(
            rec.exc_type == ClinicalDataQualityError.__name__
            for rec in result.exceptions
        )
