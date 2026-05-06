"""Unit tests for :class:`DeclineCurveReservesWorkflow`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.decline_curve_reserves_workflow import (
    DeclineCurveReservesWorkflow,
)
from pirn.tapestry import Tapestry

_SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self) -> DeclineCurveReservesWorkflow:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        return DeclineCurveReservesWorkflow(
            connection=StubHistorianConnection(),  # type: ignore[arg-type]
            oil_tag="W1.OILRATE",
            since=_SINCE,
            sample_interval_sec=60.0,
            area_acres=100.0,
            net_thickness_ft=20.0,
            porosity_fraction=0.2,
            water_saturation_fraction=0.3,
            formation_volume_factor=1.1,
            trial_count=100,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_empty_oil_tag(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "oil_tag"):
            await knot.process(
                connection=StubHistorianConnection(),
                oil_tag="",
                since=_SINCE,
                sample_interval_sec=60.0,
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                trial_count=100,
            )

    async def test_rejects_non_positive_trial_count(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "trial_count"):
            await knot.process(
                connection=StubHistorianConnection(),
                oil_tag="W1.OILRATE",
                since=_SINCE,
                sample_interval_sec=60.0,
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                trial_count=0,
            )

    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "monte_carlo" in inner.outputs
