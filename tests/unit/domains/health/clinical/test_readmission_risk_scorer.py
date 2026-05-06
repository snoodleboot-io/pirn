"""Unit tests for :class:`ReadmissionRiskScorer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.readmission_risk_scorer import (
    ReadmissionRiskScorer,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord


_CFG = KnotConfig(id="s")
_KNOT = ReadmissionRiskScorer(records=[], _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "records"):
            await _KNOT.process(records=42)  # type: ignore[arg-type]

    async def test_rejects_non_record(self) -> None:
        with self.assertRaisesRegex(TypeError, "ClinicalRecord"):
            await _KNOT.process(records=["x"])  # type: ignore[list-item]

    async def test_returns_per_patient_score_mapping(self) -> None:
        records = (
            ClinicalRecord(patient_id="P1", observation_codes=("A", "B", "C")),
        )
        out = await _KNOT.process(records=records)
        assert isinstance(out, Mapping)
        assert "P1" in out
        assert 0.0 <= out["P1"] <= 1.0
