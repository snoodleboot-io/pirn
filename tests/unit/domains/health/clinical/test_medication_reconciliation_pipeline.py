"""Unit tests for :class:`MedicationReconciliationPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.health.clinical.medication_reconciliation_pipeline import (
    MedicationReconciliationPipeline,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_drug_names(self) -> None:
        with pytest.raises(TypeError, match="drug_names"):
            MedicationReconciliationPipeline(
                drug_names=42,  # type: ignore[arg-type]
                mapping={},
                _config=KnotConfig(id="m"),
            )

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="mapping"):
            MedicationReconciliationPipeline(
                drug_names=[],
                mapping=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="m"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_runs_inner_pipeline(self) -> None:
        with Tapestry() as t:
            MedicationReconciliationPipeline(
                drug_names=["aspirin", "aspirin"],
                mapping={"aspirin": "1191"},
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, RunResult)
