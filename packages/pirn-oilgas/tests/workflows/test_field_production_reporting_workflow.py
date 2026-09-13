"""Unit tests for :class:`FieldProductionReportingWorkflow`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_oilgas.types.scada_series_spec import ScadaSeriesSpec
from pirn_oilgas.workflows.field_production_reporting_workflow import (
    FieldProductionReportingWorkflow,
)

_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_ROWS = [(datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC), float(100 + i)) for i in range(10)]

_SERIES = (
    ScadaSeriesSpec(label="oil", rows=_ROWS, tag="oil"),
    ScadaSeriesSpec(label="gas", rows=_ROWS, tag="gas"),
    ScadaSeriesSpec(label="water", rows=_ROWS, tag="water"),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FieldProductionReportingWorkflow:
        return FieldProductionReportingWorkflow(
            oil_rows=Parameter("oil_rows", list, default=_ROWS),
            gas_rows=Parameter("gas_rows", list, default=_ROWS),
            water_rows=Parameter("water_rows", list, default=_ROWS),
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
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "oil_tag"):
            await knot.process(
                oil_rows=_ROWS,
                gas_rows=_ROWS,
                water_rows=_ROWS,
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
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "gas_tag"):
            await knot.process(
                oil_rows=_ROWS,
                gas_rows=_ROWS,
                water_rows=_ROWS,
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
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "water_tag"):
            await knot.process(
                oil_rows=_ROWS,
                gas_rows=_ROWS,
                water_rows=_ROWS,
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
        assert result.succeeded
        assert "wf" in result.outputs


class TestProcessSeries(unittest.IsolatedAsyncioTestCase):
    """Coverage for the new ``series`` input (PIR-856)."""

    def _make_knot_with_series(self) -> FieldProductionReportingWorkflow:
        return FieldProductionReportingWorkflow(
            series=_SERIES,
            since=_SINCE,
            sample_interval_sec=60.0,
            forecast_months=12,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            decline_window_days=90,
            _config=KnotConfig(id="wf_series"),
        )

    async def test_series_input_builds_pipeline(self) -> None:
        knot = self._make_knot_with_series()
        result = await knot.process(
            oil_rows=None,
            gas_rows=None,
            water_rows=None,
            oil_tag=None,
            gas_tag=None,
            water_tag=None,
            series=_SERIES,
            since=_SINCE,
            sample_interval_sec=60.0,
            forecast_months=12,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            decline_window_days=90,
        )
        assert result is not None

    async def test_inner_pipeline_runs_with_series(self) -> None:
        with Tapestry() as t:
            self._make_knot_with_series()
        result = await t.run(RunRequest())
        assert result.succeeded
        assert "wf_series" in result.outputs

    async def test_rejects_both_series_and_legacy(self) -> None:
        knot = self._make_knot_with_series()
        with self.assertRaisesRegex(ValueError, "not both"):
            await knot.process(
                oil_rows=_ROWS,
                gas_rows=_ROWS,
                water_rows=_ROWS,
                oil_tag="oil",
                gas_tag="gas",
                water_tag="water",
                series=_SERIES,
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )

    async def test_rejects_neither_series_nor_legacy(self) -> None:
        knot = self._make_knot_with_series()
        with self.assertRaisesRegex(ValueError, "must supply"):
            await knot.process(
                oil_rows=None,
                gas_rows=None,
                water_rows=None,
                oil_tag=None,
                gas_tag=None,
                water_tag=None,
                series=None,
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )

    async def test_rejects_series_missing_a_label(self) -> None:
        knot = self._make_knot_with_series()
        incomplete_series = (
            ScadaSeriesSpec(label="oil", rows=_ROWS, tag="oil"),
            ScadaSeriesSpec(label="gas", rows=_ROWS, tag="gas"),
        )
        with self.assertRaisesRegex(ValueError, "missing labels"):
            await knot.process(
                oil_rows=None,
                gas_rows=None,
                water_rows=None,
                oil_tag=None,
                gas_tag=None,
                water_tag=None,
                series=incomplete_series,
                since=_SINCE,
                sample_interval_sec=60.0,
                forecast_months=12,
                max_oil_rate_bopd=10000.0,
                max_gas_rate_mscfd=20000.0,
                max_water_rate_bwpd=5000.0,
                decline_window_days=90,
            )
