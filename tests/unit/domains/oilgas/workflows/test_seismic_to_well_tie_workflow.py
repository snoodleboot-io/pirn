"""Unit tests for :class:`SeismicToWellTieWorkflow`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.seismic_to_well_tie_workflow import (
    SeismicToWellTieWorkflow,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_segy_path(self) -> None:
        with pytest.raises(ValueError, match="segy_path"):
            SeismicToWellTieWorkflow(
                segy_path="",
                volume_id="vol",
                las_path="/x.las",
                well_id="W",
                las_curves=("GR",),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
                _config=KnotConfig(id="wf"),
            )

    def test_rejects_empty_las_curves(self) -> None:
        with pytest.raises(ValueError, match="las_curves"):
            SeismicToWellTieWorkflow(
                segy_path="/x.sgy",
                volume_id="vol",
                las_path="/x.las",
                well_id="W",
                las_curves=(),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
                _config=KnotConfig(id="wf"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            SeismicToWellTieWorkflow(
                segy_path="/x.sgy",
                volume_id="vol",
                las_path="/x.las",
                well_id="W",
                las_curves=("GR",),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
                _config=KnotConfig(id="wf"),
            )
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "velocity" in inner.outputs
        assert inner.outputs["velocity"] == 2200.0
