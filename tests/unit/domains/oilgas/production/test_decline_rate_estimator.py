"""Unit tests for :class:`DeclineRateEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.decline_rate_estimator import DeclineRateEstimator
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="rate")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, window_days: int = 90) -> DeclineRateEstimator:
        return DeclineRateEstimator(
            rate_series=None,  # type: ignore[arg-type]
            window_days=window_days,
            _config=KnotConfig(id="dr", validate_io=False),
        )

    async def test_rejects_non_positive_window(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_days"):
            await knot.process(rate_series=_SERIES, window_days=0)

    async def test_returns_rate(self) -> None:
        knot = self._make_knot(window_days=90)
        out = await knot.process(rate_series=_SERIES, window_days=90)
        assert isinstance(out, float)
        assert out == 0.15
