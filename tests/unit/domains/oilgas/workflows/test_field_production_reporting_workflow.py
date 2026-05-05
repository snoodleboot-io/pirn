"""Unit tests for :class:`FieldProductionReportingWorkflow`."""

from __future__ import annotations

from datetime import datetime
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.field_production_reporting_workflow import (
    FieldProductionReportingWorkflow,
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
            FieldProductionReportingWorkflow(
                connection="not-a-conn",  # type: ignore[arg-type]
                oil_tag="o",
                gas_tag="g",
                water_tag="w",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
                _config=KnotConfig(id="wf"),
            )

    def test_rejects_empty_gas_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "gas_tag"):
            FieldProductionReportingWorkflow(
                connection=self.stub_historian,  # type: ignore[arg-type]
                oil_tag="o",
                gas_tag="",
                water_tag="w",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
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
            FieldProductionReportingWorkflow(
                connection=self.stub_historian,  # type: ignore[arg-type]
                oil_tag="oil",
                gas_tag="gas",
                water_tag="water",
                since=self.fixed_since,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
                _config=KnotConfig(id="wf"),
            )
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "forecast" in inner.outputs
