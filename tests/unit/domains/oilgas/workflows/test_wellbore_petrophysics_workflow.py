"""Unit tests for :class:`WellborePetrophysicsWorkflow`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.wellbore_petrophysics_workflow import (
    WellborePetrophysicsWorkflow,
)
from pirn.tapestry import Tapestry


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self) -> WellborePetrophysicsWorkflow:
        return WellborePetrophysicsWorkflow(
            file_path="/x.las",
            well_id="W",
            curves=("GR", "RHOB", "NPHI"),
            required_curves=("GR",),
            target_depth_step=0.5,
            rw=0.05,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_empty_file_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "file_path"):
            await knot.process(
                file_path="",
                well_id="W",
                curves=("GR", "RHOB", "NPHI"),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_rejects_empty_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "curves"):
            await knot.process(
                file_path="/x.las",
                well_id="W",
                curves=(),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_rejects_empty_required_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "required_curves"):
            await knot.process(
                file_path="/x.las",
                well_id="W",
                curves=("GR",),
                required_curves=(),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_inner_pipeline_completes(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "lithology" in inner.outputs
