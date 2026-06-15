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
