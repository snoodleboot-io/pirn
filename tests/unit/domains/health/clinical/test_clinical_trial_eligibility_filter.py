"""Unit tests for :class:`ClinicalTrialEligibilityFilter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.clinical_trial_eligibility_filter import (
    ClinicalTrialEligibilityFilter,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_records(self) -> None:
        with pytest.raises(TypeError, match="records"):
            ClinicalTrialEligibilityFilter(
                records=42,  # type: ignore[arg-type]
                criteria={},
                _config=KnotConfig(id="f"),
            )

    def test_rejects_non_record(self) -> None:
        with pytest.raises(TypeError, match="ClinicalRecord"):
            ClinicalTrialEligibilityFilter(
                records=["x"],  # type: ignore[list-item]
                criteria={},
                _config=KnotConfig(id="f"),
            )

    def test_rejects_non_mapping_criteria(self) -> None:
        with pytest.raises(TypeError, match="criteria"):
            ClinicalTrialEligibilityFilter(
                records=(),
                criteria=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="f"),
            )

    def test_rejects_non_callable_criterion(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            ClinicalTrialEligibilityFilter(
                records=(),
                criteria={"c1": "not-callable"},  # type: ignore[dict-item]
                _config=KnotConfig(id="f"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_filters_using_predicate(self) -> None:
        records = (
            ClinicalRecord(patient_id="A"),
            ClinicalRecord(patient_id="B"),
        )
        with Tapestry() as t:
            ClinicalTrialEligibilityFilter(
                records=records,
                criteria={"keep_a": lambda r: r.patient_id == "A"},
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, tuple)
        assert len(out) == 1
        assert out[0].patient_id == "A"
