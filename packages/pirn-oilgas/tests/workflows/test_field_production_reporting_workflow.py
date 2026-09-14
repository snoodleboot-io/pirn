"""Unit tests for :class:`FieldProductionReportingWorkflow`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
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


def _series_with_empty_tag(label: str) -> tuple[ScadaSeriesSpec, ...]:
    return tuple(
        ScadaSeriesSpec(
            label=spec.label, rows=spec.rows, tag="" if spec.label == label else spec.tag
        )
        for spec in _SERIES
    )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FieldProductionReportingWorkflow:
        return FieldProductionReportingWorkflow(
            series=_SERIES,
            since=_SINCE,
            sample_interval_sec=60.0,
            forecast_months=12,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            decline_window_days=90,
            _config=KnotConfig(id="wf"),
        )

    async def _process(self, series: Any) -> Any:
        return await self._make_knot().process(
            series=series,
            since=_SINCE,
            sample_interval_sec=60.0,
            forecast_months=12,
            max_oil_rate_bopd=10000.0,
            max_gas_rate_mscfd=20000.0,
            max_water_rate_bwpd=5000.0,
            decline_window_days=90,
        )

    async def test_series_input_builds_pipeline(self) -> None:
        result = await self._process(_SERIES)
        assert result is not None

    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        result = await t.run(RunRequest())
        assert result.succeeded
        assert "wf" in result.outputs

    async def test_rejects_empty_oil_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "oil series tag"):
            await self._process(_series_with_empty_tag("oil"))

    async def test_rejects_empty_gas_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "gas series tag"):
            await self._process(_series_with_empty_tag("gas"))

    async def test_rejects_empty_water_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "water series tag"):
            await self._process(_series_with_empty_tag("water"))

    async def test_rejects_series_missing_a_label(self) -> None:
        incomplete_series = (
            ScadaSeriesSpec(label="oil", rows=_ROWS, tag="oil"),
            ScadaSeriesSpec(label="gas", rows=_ROWS, tag="gas"),
        )
        with self.assertRaisesRegex(ValueError, r"missing labels \['water'\]"):
            await self._process(incomplete_series)

    async def test_rejects_series_that_is_not_a_tuple(self) -> None:
        with self.assertRaisesRegex(TypeError, "tuple of ScadaSeriesSpec"):
            await self._process(list(_SERIES))

    async def test_rejects_series_with_a_non_spec_entry(self) -> None:
        with self.assertRaisesRegex(TypeError, "tuple of ScadaSeriesSpec"):
            await self._process((*_SERIES[:2], {"label": "water"}))
