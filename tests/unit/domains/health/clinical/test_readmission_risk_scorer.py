"""Unit tests for :class:`ReadmissionRiskScorer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.readmission_risk_scorer import (
    ReadmissionRiskScorer,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "records"):
            ReadmissionRiskScorer(
                records=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_record(self) -> None:
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            ReadmissionRiskScorer(
                records=["x"],  # type: ignore[list-item]
                _config=KnotConfig(id="s"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_patient_score_mapping(self) -> None:
        records = (
            ClinicalRecord(patient_id="P1", observation_codes=("A", "B", "C")),
        )
        with Tapestry() as t:
            ReadmissionRiskScorer(
                records=records,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, Mapping)
        assert "P1" in out
        assert 0.0 <= out["P1"] <= 1.0
