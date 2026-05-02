"""Unit tests for :class:`WellborePetrophysicsWorkflow`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.wellbore_petrophysics_workflow import (
    WellborePetrophysicsWorkflow,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_file_path(self) -> None:
        with pytest.raises(ValueError, match="file_path"):
            WellborePetrophysicsWorkflow(
                file_path="",
                well_id="W",
                curves=("GR", "RHOB", "NPHI"),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
                _config=KnotConfig(id="wf"),
            )

    def test_rejects_empty_curves(self) -> None:
        with pytest.raises(ValueError, match="curves"):
            WellborePetrophysicsWorkflow(
                file_path="/x.las",
                well_id="W",
                curves=(),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
                _config=KnotConfig(id="wf"),
            )

    def test_rejects_empty_required_curves(self) -> None:
        with pytest.raises(ValueError, match="required_curves"):
            WellborePetrophysicsWorkflow(
                file_path="/x.las",
                well_id="W",
                curves=("GR",),
                required_curves=(),
                target_depth_step=0.5,
                rw=0.05,
                _config=KnotConfig(id="wf"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_inner_pipeline_completes(self) -> None:
        with Tapestry() as t:
            WellborePetrophysicsWorkflow(
                file_path="/x.las",
                well_id="W",
                curves=("GR", "RHOB", "NPHI"),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
                _config=KnotConfig(id="wf"),
            )
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "lithology" in inner.outputs
