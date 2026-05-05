"""Unit tests for :class:`DeclineCurveReservesWorkflow`."""

from __future__ import annotations

from datetime import datetime
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.decline_curve_reserves_workflow import (
    DeclineCurveReservesWorkflow,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):

    def setUp(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        self.stub_historian = StubHistorianConnection()
        from datetime import datetime, timezone
        self.fixed_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def test_rejects_non_historian_connection(self) -> None:
        with self.assertRaisesRegex(TypeError, "connection"):
            DeclineCurveReservesWorkflow(
                connection="not-a-conn",  # type: ignore[arg-type]
                oil_tag="W1.OILRATE",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                trial_count=100,
                _config=KnotConfig(id="wf"),
            )

    def test_rejects_empty_oil_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "oil_tag"):
            DeclineCurveReservesWorkflow(
                connection=self.stub_historian,  # type: ignore[arg-type]
                oil_tag="",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                trial_count=100,
                _config=KnotConfig(id="wf"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        self.stub_historian = StubHistorianConnection()
        from datetime import datetime, timezone
        self.fixed_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            DeclineCurveReservesWorkflow(
                connection=self.stub_historian,  # type: ignore[arg-type]
                oil_tag="W1.OILRATE",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                area_acres=100.0,
                net_thickness_ft=20.0,
                porosity_fraction=0.2,
                water_saturation_fraction=0.3,
                formation_volume_factor=1.1,
                trial_count=100,
                _config=KnotConfig(id="wf"),
            )
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "monte_carlo" in inner.outputs
