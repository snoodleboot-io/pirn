"""Unit tests for :class:`FieldProductionReportingWorkflow`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.domains.oilgas.workflows.field_production_reporting_workflow import (
    FieldProductionReportingWorkflow,
)
from pirn.tapestry import Tapestry

_SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self) -> FieldProductionReportingWorkflow:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        return FieldProductionReportingWorkflow(
            connection=StubHistorianConnection(),  # type: ignore[arg-type]
            oil_tag="oil",
            gas_tag="gas",
            water_tag="water",
            since=_SINCE,
            sample_interval_sec=60.0,
            forecast_months=12,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            decline_window_days=90,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_empty_oil_tag(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "oil_tag"):
            await knot.process(
                connection=StubHistorianConnection(),
                oil_tag="",
                gas_tag="gas",
                water_tag="water",
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )

    async def test_rejects_empty_gas_tag(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "gas_tag"):
            await knot.process(
                connection=StubHistorianConnection(),
                oil_tag="oil",
                gas_tag="",
                water_tag="water",
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )

    async def test_rejects_empty_water_tag(self) -> None:
        from tests.unit.domains.oilgas.conftest import StubHistorianConnection
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "water_tag"):
            await knot.process(
                connection=StubHistorianConnection(),
                oil_tag="oil",
                gas_tag="gas",
                water_tag="",
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )

    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        result = await t.run(RunRequest())
        inner = result.outputs["wf"]
        assert isinstance(inner, RunResult)
        assert inner.succeeded
        assert "forecast" in inner.outputs
