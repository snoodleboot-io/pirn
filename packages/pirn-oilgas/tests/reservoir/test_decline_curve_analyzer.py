"""Unit tests for :class:`DeclineCurveAnalyzer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="s", sample_count=12, sample_interval_sec=86400.0),
    data=np.linspace(1000.0, 400.0, 12),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, method: str = "hyperbolic") -> DeclineCurveAnalyzer:
        return DeclineCurveAnalyzer(
            rate_series=None,  # type: ignore[arg-type]
            method=method,
            _config=KnotConfig(id="dca", validate_io=False),
        )

    async def test_rejects_invalid_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(rate_series=_SERIES, method="bogus")

    async def test_returns_decline_params(self) -> None:
        knot = self._make_knot()
        out = await knot.process(rate_series=_SERIES, method="hyperbolic")
        assert "qi" in out
        assert "di_per_year" in out
        assert "b" in out


class TestHyperbolicFitIsReal(unittest.IsolatedAsyncioTestCase):
    """The hyperbolic branch fits the Arps curve or raises — it never degrades silently."""

    @staticmethod
    def _arps(qi: float, di_day: float, b: float, days: int) -> ScadaPayload:
        """A rate series generated from Arps (1945) eq. 3 with known parameters."""
        time_days = np.arange(days, dtype=np.float64)
        rates = qi * (1.0 + b * di_day * time_days) ** (-1.0 / b)
        return ScadaPayload(
            metadata=ScadaTimeSeries(sensor_id="s", sample_count=days, sample_interval_sec=86400.0),
            data=rates,
        )

    def _knot(self) -> DeclineCurveAnalyzer:
        return DeclineCurveAnalyzer(
            rate_series=None,  # type: ignore[arg-type]
            method="hyperbolic",
            _config=KnotConfig(id="dca", validate_io=False),
        )

    async def test_recovers_the_arps_parameters_it_was_generated_from(self) -> None:
        # Arrange: two years of a known hyperbolic decline.
        series = self._arps(qi=1000.0, di_day=0.002, b=0.6, days=730)

        # Act
        out = await self._knot().process(rate_series=series, method="hyperbolic")

        # Assert: the generating parameters come back, not an exponential stand-in.
        assert abs(out["qi"] - 1000.0) < 1.0
        assert abs(out["di_per_year"] - 0.002 * 365.0) < 0.01
        assert abs(out["b"] - 0.6) < 0.01

    async def test_non_converging_series_raises_instead_of_reporting_b_zero(self) -> None:
        series = self._arps(qi=1000.0, di_day=0.002, b=0.6, days=30)
        series.data[5] = float("nan")

        with self.assertRaisesRegex(ValueError, "did not converge"):
            await self._knot().process(rate_series=series, method="hyperbolic")
