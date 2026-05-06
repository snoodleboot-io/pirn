"""Unit tests for :class:`MedicationReconciliationPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical.medication_reconciliation_pipeline import (
    MedicationReconciliationPipeline,
)


_CFG = KnotConfig(id="m")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_drug_names(self) -> None:
        knot = MedicationReconciliationPipeline(drug_names=[], mapping={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "drug_names"):
            await knot.process(drug_names=42, mapping={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping(self) -> None:
        knot = MedicationReconciliationPipeline(drug_names=[], mapping={}, _config=_CFG)
        with self.assertRaisesRegex(TypeError, "mapping"):
            await knot.process(drug_names=[], mapping=42)  # type: ignore[arg-type]

    async def test_runs_inner_pipeline(self) -> None:
        knot = MedicationReconciliationPipeline(
            drug_names=["aspirin", "aspirin"],
            mapping={"aspirin": "1191"},
            _config=_CFG,
        )
        out = await knot.process(
            drug_names=["aspirin", "aspirin"],
            mapping={"aspirin": "1191"},
        )
        assert isinstance(out, RunResult)
