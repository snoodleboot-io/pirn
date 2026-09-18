"""Unit tests for :class:`TypeCurveFitter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn_oilgas.types.scada_payload import ScadaPayload
from pirn_oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="s", sample_count=12, sample_interval_sec=86400.0),
    data=np.linspace(1000.0, 400.0, 12),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TypeCurveFitter:
        return TypeCurveFitter(
            rate_series=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="tc", validate_io=False),
        )

    async def test_returns_eur(self) -> None:
        knot = self._make_knot()
        out = await knot.process(rate_series=_SERIES)
        assert "qi" in out
        assert "eur_stb" in out


class TestTypeCurveFitIsReal(unittest.IsolatedAsyncioTestCase):
    """The fit is hyperbolic or it raises — no exponential stand-in behind the EUR."""

    @staticmethod
    def _arps(qi: float, di_day: float, b: float, days: int) -> ScadaPayload:
        time_days = np.arange(days, dtype=np.float64)
        rates = qi * (1.0 + b * di_day * time_days) ** (-1.0 / b)
        return ScadaPayload(
            metadata=ScadaTimeSeries(sensor_id="s", sample_count=days, sample_interval_sec=86400.0),
            data=rates,
        )

    def _knot(self) -> TypeCurveFitter:
        return TypeCurveFitter(
            rate_series=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="tc", validate_io=False),
        )

    async def test_recovers_the_generating_parameters_and_the_arps_eur(self) -> None:
        # Arrange: a known hyperbolic decline; its EUR to q_aban = 1 BOPD follows
        # Robertson (1988): qi^b / (Di (1-b)) * (qi^(1-b) - q_aban^(1-b)).
        qi, di_day, b = 1000.0, 0.002, 0.6
        series = self._arps(qi=qi, di_day=di_day, b=b, days=730)
        expected_eur = (qi**b / (di_day * (1.0 - b))) * (qi ** (1.0 - b) - 1.0 ** (1.0 - b))

        # Act
        out = await self._knot().process(rate_series=series)

        # Assert
        assert abs(out["b"] - b) < 0.01
        assert abs(out["eur_stb"] - expected_eur) / expected_eur < 0.01

    async def test_non_converging_series_raises_instead_of_an_exponential_eur(self) -> None:
        series = self._arps(qi=1000.0, di_day=0.002, b=0.6, days=30)
        series.data[3] = float("nan")

        with self.assertRaisesRegex(ValueError, "did not converge"):
            await self._knot().process(rate_series=series)
