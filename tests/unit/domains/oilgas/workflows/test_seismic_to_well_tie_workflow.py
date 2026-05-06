"""Unit tests for :class:`SeismicToWellTieWorkflow`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.seismic_to_well_tie_workflow import (
    SeismicToWellTieWorkflow,
)
from pirn.tapestry import Tapestry


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self) -> SeismicToWellTieWorkflow:
        return SeismicToWellTieWorkflow(
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

    async def test_rejects_empty_segy_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "segy_path"):
            await knot.process(
                segy_path="",
                volume_id="vol",
                las_path="/x.las",
                well_id="W",
                las_curves=("GR",),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
            )

    async def test_rejects_empty_las_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "las_curves"):
            await knot.process(
                segy_path="/x.sgy",
                volume_id="vol",
                las_path="/x.las",
                well_id="W",
                las_curves=(),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
            )

    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "velocity" in inner.outputs
        assert inner.outputs["velocity"] == 2200.0
